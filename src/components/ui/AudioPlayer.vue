<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{ src: string }>()
const audioRef = ref<HTMLAudioElement | null>(null)

onMounted(() => {
  if (audioRef.value) {
    audioRef.value.volume = 1
  }
})
</script>

<template>
  <div class="w-full max-w-md mx-auto p-6 bg-#475569 rounded-2xl shadow-lg border border-border">
    <div class="text-sm text-muted-foreground mb-2">Vista previa</div>
    <div class="relative w-full">
      <audio
        ref="audioRef"
        :src="props.src"
        controls
        
      >
        Your browser does not support the audio element.
      </audio>
    </div>
  </div>
</template>