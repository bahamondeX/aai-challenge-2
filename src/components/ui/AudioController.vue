<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted, defineExpose } from 'vue'

const props = defineProps<{
  src: string
  autoplay?: boolean
  loop?: boolean
}>()

const emit = defineEmits<{
  play: []
  pause: []
  ended: []
  timeupdate: [number]
  durationchange: [number]
  volumechange: [number]
}>()

const audio = ref<HTMLAudioElement | null>(null)

const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const isMuted = ref(false)

const play = async () => {
  try {
    await audio.value?.play()
  } catch (e) {
    console.warn('Play failed', e)
  }
}
const pause = () => audio.value?.pause()
const togglePlay = async () => isPlaying.value ? pause() : await play()
const setVolume = (vol: number) => {
  if (audio.value) audio.value.volume = vol
}
const toggleMute = () => {
  if (!audio.value) return
  isMuted.value = !isMuted.value
  audio.value.muted = isMuted.value
}
const seek = (time: number) => {
  if (audio.value && isFinite(time)) {
    audio.value.currentTime = time
  }
}

onMounted(() => {
  if (!audio.value) return
  if (props.autoplay) play()
})

watch(() => props.src, () => {
  currentTime.value = 0
  duration.value = 0
})

onUnmounted(() => {
  audio.value?.pause()
})

// Eventos del elemento <audio>
const onTimeUpdate = () => {
  currentTime.value = audio.value?.currentTime || 0
  emit('timeupdate', currentTime.value)
}
const onPlay = () => {
  isPlaying.value = true
  emit('play')
}
const onPause = () => {
  isPlaying.value = false
  emit('pause')
}
const onEnded = () => {
  isPlaying.value = false
  emit('ended')
}
const onDurationChange = () => {
  duration.value = audio.value?.duration || 0
  emit('durationchange', duration.value)
}
const onVolumeChange = () => {
  volume.value = audio.value?.volume || 1
  emit('volumechange', volume.value)
  isMuted.value = audio.value?.muted || false
}

defineExpose({
  audio,
  isPlaying,
  currentTime,
  duration,
  volume,
  isMuted,
  play,
  pause,
  togglePlay,
  toggleMute,
  seek,
  setVolume,
})
</script>

<template>
  <audio
    ref="audio"
    :src="src"
    :loop="loop"
    hidden
    @timeupdate="onTimeUpdate"
    @play="onPlay"
    @pause="onPause"
    @ended="onEnded"
    @durationchange="onDurationChange"
    @volumechange="onVolumeChange"
  />
</template>