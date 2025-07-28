<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

type Props = {
  mimeType?: string
  audioBitsPerSecond?: number
  timeslice?: number
  autoGainControl?: boolean
  echoCancellation?: boolean
  noiseSuppression?: boolean
  handleData?: (audio: Blob) => any
  websocketUrl?: string
  enableTranscription?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  mimeType: 'audio/webm;codecs=opus',
  audioBitsPerSecond: 128000,
  timeslice: 100,  // Reduced for lower latency
  autoGainControl: true,
  echoCancellation: true,
  noiseSuppression: true,
  enableTranscription: false,
  websocketUrl: 'ws://localhost:8000/ws/transcribe'
})

const emit = defineEmits<{
  start: []
  stop: [blob: Blob, url: string]
  pause: []
  resume: []
  dataAvailable: [chunk: Blob]
  error: [error: string]
  deviceChange: [deviceId: string]
  recordingTime: [seconds: number]
  transcript: [text: string]
  transcriptionError: [error: string]
}>()

// State
const websocket = ref<WebSocket | null>(null)
const transcriptionText = ref('')
const isTranscribing = ref(false)
const devices = ref<MediaDeviceInfo[]>([])
const selectedDeviceId = ref<string>('')
const hasPermission = ref(false)
const stream = ref<MediaStream | null>(null)
const recorder = ref<MediaRecorder | null>(null)
const chunks = ref<Blob[]>([])
const isRecording = ref(false)
const isPaused = ref(false)
const recordingTime = ref(0)
const recordingTimer = ref<number | null>(null)

// Audio processing for transcription
const audioContext = ref<AudioContext | null>(null)
const processorNode = ref<ScriptProcessorNode | null>(null)
const sourceNode = ref<MediaStreamAudioSourceNode | null>(null)

// Visualization
const animationId = ref<number | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const analyser = ref<AnalyserNode | null>(null)
const dataArray = ref<Uint8Array | null>(null)
const currentLevel = ref(0)
const peakLevel = ref(0)
const levelHistory = ref<number[]>([])

const recordingUrl = computed(() =>
  chunks.value.length
    ? URL.createObjectURL(new Blob(chunks.value, { type: props.mimeType }))
    : ''
)

const formattedTime = computed(() => {
  const mins = Math.floor(recordingTime.value / 60)
  const secs = recordingTime.value % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
})

const canRecord = computed(() => 
  hasPermission.value && selectedDeviceId.value && !isRecording.value && !isPaused.value
)

const canPause = computed(() => isRecording.value)
const canResume = computed(() => isPaused.value)
const canStop = computed(() => isRecording.value || isPaused.value)

// WebSocket optimized connection
const setupWebSocket = () => {
  if (!props.enableTranscription || !props.websocketUrl) return

  try {
    websocket.value = new WebSocket(props.websocketUrl)
    websocket.value.binaryType = 'arraybuffer'
    
    websocket.value.onopen = () => {
      isTranscribing.value = true
    }
    
    websocket.value.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        
        if (message.type === 'transcript') {
          transcriptionText.value = message.text
          emit('transcript', message.text)
        } else if (message.type === 'error') {
          emit('transcriptionError', message.message)
        }
      } catch (e) {
        emit('transcriptionError', 'Failed to parse transcription response')
      }
    }
    
    websocket.value.onerror = () => {
      emit('transcriptionError', 'WebSocket connection error')
      isTranscribing.value = false
    }
    
    websocket.value.onclose = () => {
      isTranscribing.value = false
    }
  } catch (e) {
    emit('transcriptionError', 'Failed to create WebSocket connection')
  }
}

const closeWebSocket = () => {
  if (websocket.value) {
    if (websocket.value.readyState === WebSocket.OPEN) {
      websocket.value.send(JSON.stringify({ type: 'stop' }))
    }
    websocket.value.close()
    websocket.value = null
    isTranscribing.value = false
  }
}

// Initialize devices
const initializeDevices = async (): Promise<void> => {
  try {
    const deviceList = await navigator.mediaDevices.enumerateDevices()
    devices.value = deviceList.filter(device => device.kind === 'audioinput')
    
    if (devices.value.length > 0 && !selectedDeviceId.value) {
      selectedDeviceId.value = devices.value[0].deviceId
    }
  } catch (error) {
    emit('error', 'Failed to enumerate devices')
  }
}

// Request permission
const requestPermission = async (): Promise<void> => {
  try {
    const testStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: selectedDeviceId.value ? { exact: selectedDeviceId.value } : undefined,
        autoGainControl: props.autoGainControl,
        echoCancellation: props.echoCancellation,
        noiseSuppression: props.noiseSuppression,
        sampleRate: 16000,
        channelCount: 1
      }
    })
    testStream.getTracks().forEach(track => track.stop())
    hasPermission.value = true
    await initializeDevices()
  } catch (error) {
    hasPermission.value = false
    emit('error', 'Microphone permission denied')
  }
}

// Create optimized audio stream
const createStream = async (): Promise<MediaStream | null> => {
  if (!hasPermission.value || !selectedDeviceId.value) return null

  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: { exact: selectedDeviceId.value },
        autoGainControl: props.autoGainControl,
        echoCancellation: props.echoCancellation,
        noiseSuppression: props.noiseSuppression,
        sampleRate: 16000,
        channelCount: 1
      }
    })
  } catch (error) {
    emit('error', 'Failed to access microphone')
    return null
  }
}

// Setup real-time audio processing for transcription
const setupRealtimeProcessing = (mediaStream: MediaStream): void => {
  if (!props.enableTranscription) return

  try {
    audioContext.value = new AudioContext({ 
      sampleRate: 16000,
      latencyHint: 'interactive'
    })
    
    sourceNode.value = audioContext.value.createMediaStreamSource(mediaStream)
    
    // Use smaller buffer for lower latency
    processorNode.value = audioContext.value.createScriptProcessor(1024, 1, 1)
    
    processorNode.value.onaudioprocess = (event) => {
      if (websocket.value?.readyState === WebSocket.OPEN) {
        const inputBuffer = event.inputBuffer.getChannelData(0)
        const pcmData = new Int16Array(inputBuffer.length)
        
        // Convert float32 to int16
        for (let i = 0; i < inputBuffer.length; i++) {
          pcmData[i] = Math.max(-32768, Math.min(32767, inputBuffer[i] * 32767))
        }
        
        const base64Audio = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)))
        websocket.value.send(JSON.stringify({
          type: 'audio',
          data: base64Audio
        }))
      }
    }
    
    sourceNode.value.connect(processorNode.value)
    processorNode.value.connect(audioContext.value.destination)
    
  } catch (error) {
    emit('error', 'Failed to setup real-time processing')
  }
}

// Setup optimized audio analysis
const setupAnalyser = (mediaStream: MediaStream): void => {
  try {
    if (!audioContext.value) {
      audioContext.value = new AudioContext({ 
        sampleRate: 16000,
        latencyHint: 'interactive'
      })
    }
    
    if (!sourceNode.value) {
      sourceNode.value = audioContext.value.createMediaStreamSource(mediaStream)
    }
    
    analyser.value = audioContext.value.createAnalyser()
    analyser.value.fftSize = 1024 // Smaller for better performance
    analyser.value.smoothingTimeConstant = 0.3 // Faster response

    dataArray.value = new Uint8Array(analyser.value.frequencyBinCount)
    sourceNode.value.connect(analyser.value)

    startVisualization()
  } catch (error) {
    emit('error', 'Failed to setup audio analysis')
  }
}

// Optimized visualization with throttling
let lastFrameTime = 0
const FRAME_RATE = 30 // 30 FPS for smooth but efficient animation

const startVisualization = (): void => {
  if (!analyser.value || !dataArray.value || !canvasRef.value) return

  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')!
  const width = canvas.width
  const height = canvas.height

  const draw = (currentTime: number): void => {
    if (!analyser.value || !dataArray.value) return

    // Throttle to target frame rate
    if (currentTime - lastFrameTime >= 1000 / FRAME_RATE) {
      // Get frequency data for level meter
      analyser.value.getByteFrequencyData(dataArray.value)
      const average = dataArray.value.reduce((sum, value) => sum + value, 0) / dataArray.value.length
      currentLevel.value = Math.round((average / 255) * 100)
      peakLevel.value = Math.max(peakLevel.value * 0.95, currentLevel.value)

      // Store level history (limit size)
      levelHistory.value.push(currentLevel.value)
      if (levelHistory.value.length > width / 4) {
        levelHistory.value.shift()
      }

      // Get time domain data for waveform
      analyser.value.getByteTimeDomainData(dataArray.value)

      // Clear canvas
      ctx.fillStyle = '#0f172a'
      ctx.fillRect(0, 0, width, height)

      // Draw waveform
      ctx.lineWidth = 2
      ctx.strokeStyle = isRecording.value ? '#10b981' : '#64748b'
      ctx.beginPath()

      const sliceWidth = width / dataArray.value.length
      let x = 0

      for (let i = 0; i < dataArray.value.length; i++) {
        const v = dataArray.value[i] / 128.0
        const y = (v * height) / 2

        if (i === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
        x += sliceWidth
      }

      ctx.lineTo(width, height / 2)
      ctx.stroke()

      // Draw level history
      if (levelHistory.value.length > 1) {
        ctx.strokeStyle = isRecording.value ? '#34d399' : '#94a3b8'
        ctx.lineWidth = 1
        ctx.beginPath()
        
        levelHistory.value.forEach((level, index) => {
          const x = width - (levelHistory.value.length - index) * 4
          const y = height - (level / 100) * (height * 0.3)
          
          if (index === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.stroke()
      }

      lastFrameTime = currentTime
    }

    animationId.value = requestAnimationFrame(draw)
  }

  animationId.value = requestAnimationFrame(draw)
}

const stopVisualization = (): void => {
  if (animationId.value) {
    cancelAnimationFrame(animationId.value)
    animationId.value = null
  }
}

// Recording timer
const startTimer = (): void => {
  recordingTime.value = 0
  recordingTimer.value = window.setInterval(() => {
    recordingTime.value++
    emit('recordingTime', recordingTime.value)
  }, 1000)
}

const stopTimer = (): void => {
  if (recordingTimer.value) {
    clearInterval(recordingTimer.value)
    recordingTimer.value = null
  }
}

// Optimized recording controls
const startRecording = async (): Promise<void> => {
  if (!canRecord.value) return

  try {
    stream.value = await createStream()
    if (!stream.value) return

    setupAnalyser(stream.value)

    if (props.enableTranscription) {
      setupWebSocket()
      setupRealtimeProcessing(stream.value)
    }

    recorder.value = new MediaRecorder(stream.value, {
      mimeType: props.mimeType,
      audioBitsPerSecond: props.audioBitsPerSecond
    })

    chunks.value = []

    recorder.value.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunks.value.push(event.data)
        emit('dataAvailable', event.data)
        
        if (props.handleData) {
          props.handleData(event.data)
        }
      }
    }

    recorder.value.onstop = () => {
      const blob = new Blob(chunks.value, { type: props.mimeType })
      emit('stop', blob, URL.createObjectURL(blob))
      
      if (props.handleData) {
        props.handleData(blob)
      }
      cleanup()
    }

    recorder.value.onerror = (event: any) => {
      emit('error', `Recording error: ${event.error}`)
      cleanup()
    }

    recorder.value.start(props.timeslice)
    isRecording.value = true
    startTimer()
    emit('start')

  } catch (error) {
    emit('error', 'Failed to start recording')
    cleanup()
  }
}

const pauseRecording = (): void => {
  if (!canPause.value || !recorder.value) return

  recorder.value.pause()
  isPaused.value = true
  isRecording.value = false
  stopTimer()
  emit('pause')
  
  if (props.handleData) {
    props.handleData(new Blob(chunks.value, { type: props.mimeType }))
  }
}

const resumeRecording = (): void => {
  if (!canResume.value || !recorder.value) return

  recorder.value.resume()
  isPaused.value = false
  isRecording.value = true
  startTimer()
  emit('resume')
}

const stopRecording = (): void => {
  if (!canStop.value || !recorder.value) return

  recorder.value.stop()
  isRecording.value = false
  isPaused.value = false
  stopTimer()
  closeWebSocket()
}

const resetRecording = (): void => {
  cleanup()
  chunks.value = []
  recordingTime.value = 0
  transcriptionText.value = ''
  
  if (recordingUrl.value) {
    URL.revokeObjectURL(recordingUrl.value)
  }
}

const cleanup = (): void => {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
    stream.value = null
  }

  if (processorNode.value) {
    processorNode.value.disconnect()
    processorNode.value = null
  }

  if (sourceNode.value) {
    sourceNode.value.disconnect()
    sourceNode.value = null
  }

  if (audioContext.value && audioContext.value.state !== 'closed') {
    audioContext.value.close()
    audioContext.value = null
  }

  closeWebSocket()
  stopVisualization()
  stopTimer()

  analyser.value = null
  dataArray.value = null
  currentLevel.value = 0
  peakLevel.value = 0
  levelHistory.value = []
}

// Device change handler
watch(selectedDeviceId, (newDeviceId) => {
  if (newDeviceId) {
    emit('deviceChange', newDeviceId)
  }
})

// Cleanup on unmount
onUnmounted(() => {
  cleanup()
  if (recordingUrl.value) {
    URL.revokeObjectURL(recordingUrl.value)
  }
})

// Initialize on mount
onMounted(async () => {
  await requestPermission()
  navigator.mediaDevices.addEventListener('devicechange', initializeDevices)
})

// Expose methods and state
defineExpose({
  startRecording,
  pauseRecording,
  resumeRecording,
  stopRecording,
  resetRecording,
  requestPermission,
  recordingUrl,
  isRecording: computed(() => isRecording.value),
  isPaused: computed(() => isPaused.value),
  recordingTime: computed(() => recordingTime.value),
  currentLevel: computed(() => currentLevel.value),
  transcriptionText: computed(() => transcriptionText.value),
  isTranscribing: computed(() => isTranscribing.value)
})
</script>

<template>
  <div class="w-full max-w-2xl mx-auto m-4 p-6 bg-slate-900 rounded-2xl border border-slate-700">
    <!-- Permission Request -->
    <div v-if="!hasPermission" class="text-center py-8">
      <div class="mb-4">
        <svg class="w-12 h-12 mx-auto text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
        </svg>
      </div>
      <p class="text-slate-300 mb-4">Microphone access required to record audio</p>
      <button
        @click="requestPermission"
        class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
      >
        Grant Permission
      </button>
    </div>

    <template v-else>
      <!-- Device Selection -->
      <div class="mb-6">
        <label class="block text-sm font-medium text-slate-300 mb-2">
          Microphone Device
        </label>
        <select
          v-model="selectedDeviceId"
          class="w-full p-3 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
        >
          <option value="" disabled>Select a microphone</option>
          <option
            v-for="device in devices"
            :key="device.deviceId"
            :value="device.deviceId"
          >
            {{ device.label || `Microphone ${device.deviceId.slice(0, 8)}...` }}
          </option>
        </select>
      </div>

      <!-- Recording Status -->
      <div class="mb-6 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <!-- Recording indicator -->
          <div class="flex items-center gap-2">
            <div
              class="w-3 h-3 rounded-full transition-colors"
              :class="{
                'bg-red-500 animate-pulse': isRecording,
                'bg-yellow-500': isPaused,
                'bg-slate-600': !isRecording && !isPaused
              }"
            ></div>
            <span class="text-sm text-slate-300">
              {{ isRecording ? 'Recording...' : isPaused ? 'Paused' : 'Ready' }}
            </span>
          </div>

          <!-- Timer -->
          <div class="text-lg font-mono text-white">
            {{ formattedTime }}
          </div>

          <!-- Transcription Status -->
          <div v-if="enableTranscription" class="flex items-center gap-2">
            <div
              class="w-2 h-2 rounded-full"
              :class="{
                'bg-green-500 animate-pulse': isTranscribing,
                'bg-slate-600': !isTranscribing
              }"
            ></div>
            <span class="text-xs text-slate-400">
              {{ isTranscribing ? 'Transcribing' : 'Not connected' }}
            </span>
          </div>
        </div>

        <!-- Level meter -->
        <div class="flex items-center gap-2">
          <span class="text-xs text-slate-400">Level:</span>
          <div class="w-20 h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-emerald-500 to-red-500 transition-all duration-100"
              :style="{ width: `${currentLevel}%` }"
            ></div>
          </div>
          <span class="text-xs text-slate-400 w-8">{{ currentLevel }}%</span>
        </div>
      </div>

      <!-- Waveform Visualization -->
      <div class="mb-6">
        <canvas
          ref="canvasRef"
          width="640"
          height="120"
          class="w-full h-30 bg-slate-800 rounded-lg border border-slate-600"
        ></canvas>
      </div>

      <!-- Controls -->
      <div class="flex flex-wrap gap-3 mb-6">
        <button
          @click="startRecording"
          :disabled="!canRecord"
          class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10"/>
          </svg>
          Start
        </button>

        <button
          @click="pauseRecording"
          :disabled="!canPause"
          class="px-6 py-2 bg-yellow-600 hover:bg-yellow-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
          </svg>
          Pause
        </button>

        <button
          @click="resumeRecording"
          :disabled="!canResume"
          class="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z"/>
          </svg>
          Resume
        </button>

        <button
          @click="stopRecording"
          class="px-6 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 18L18 6M6 6l12 12"/>
          </svg>
          Stop
        </button>
      </div>
    </template>
  </div>
</template>
