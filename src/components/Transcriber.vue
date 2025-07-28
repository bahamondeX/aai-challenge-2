<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { Button } from '~/components/ui/button';
import { Input } from '~/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '~/components/ui/card';
import { Badge } from '~/components/ui/badge';
import { ScrollArea } from '~/components/ui/scroll-area';
import { Separator } from '~/components/ui/separator';
import { ExternalLink, Play, Search, Loader2, Radio } from 'lucide-vue-next';

interface Word {
  start: number;
  end: number;
  confidence: number;
  text: string;
  word_is_final: boolean;
}

interface TurnEventData {
  type: 'Turn';
  turn_order: number;
  turn_is_formatted: boolean;
  end_of_turn: boolean;
  transcript: string;
  end_of_turn_confidence: number;
  words: Word[];
}

interface TranscriptSegment {
  text: string;
  turn: number;
  colorClass: string;
}

const searchQuery = ref<string>('');
const searchResults = ref<string[]>([]);
const streamingUrl = ref<string>('');
const transcript = ref<TranscriptSegment[]>([]);
const eventSource = ref<EventSource | null>(null);
const currentTurnWords = ref<string[]>([]);
const currentTurnOrder = ref<number>(-1);
const transcriptContainer = ref<HTMLElement | null>(null);
const isSearching = ref(false);
const isStreaming = ref(false);

const colors = [
  { text: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
  { text: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
  { text: 'text-purple-600', bg: 'bg-purple-50 border-purple-200' },
  { text: 'text-orange-600', bg: 'bg-orange-50 border-orange-200' },
  { text: 'text-rose-600', bg: 'bg-rose-50 border-rose-200' },
  { text: 'text-indigo-600', bg: 'bg-indigo-50 border-indigo-200' }
];
let colorIndex = 0;

const searchVideos = async (): Promise<void> => {
  if (!searchQuery.value) return;
  isSearching.value = true;
  try {
    const response = await fetch(`/api/search?query=${encodeURIComponent(searchQuery.value)}`);
    const data: { videos: string[] } = await response.json();
    searchResults.value = data.videos;
  } catch (error) {
    console.error('Error searching videos:', error);
    searchResults.value = [];
  } finally {
    isSearching.value = false;
  }
};

const startStreaming = (url: string): void => {
  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }

  transcript.value = [];
  currentTurnWords.value = [];
  currentTurnOrder.value = -1;
  colorIndex = 0;
  streamingUrl.value = url;
  isStreaming.value = true;

  eventSource.value = new EventSource(`/api/stream?url=${encodeURIComponent(url)}`);

  eventSource.value.onmessage = (event: MessageEvent) => {
    try {
      const data: TurnEventData = JSON.parse(event.data);
      if (data.type === 'Turn') {
        handleTurnEvent(data);
      }
    } catch (e) {
      console.error('Error parsing SSE data:', e, event.data);
    }
  };

  eventSource.value.onerror = (error: Event) => {
    console.error('EventSource failed:', error);
    eventSource.value?.close();
    eventSource.value = null;
    isStreaming.value = false;
  };

  eventSource.value.onopen = () => {
    console.log('EventSource opened');
  };
};


const handleTurnEvent = (data: TurnEventData): void => {
  const newWords = data.words || [];

  if (data.turn_order !== currentTurnOrder.value) {
    if (currentTurnWords.value.length > 0) {
      transcript.value.push({
        text: currentTurnWords.value.join(' '),
        turn: currentTurnOrder.value,
        colorClass: colors[(colorIndex - 1 + colors.length) % colors.length].text,
      });
    }
    currentTurnOrder.value = data.turn_order;
    currentTurnWords.value = [];
    colorIndex = (colorIndex + 1) % colors.length;
  }

  newWords.forEach(word => {
    if (word.word_is_final && !currentTurnWords.value.includes(word.text)) {
      currentTurnWords.value.push(word.text);
    }
  });

  if (data.end_of_turn && currentTurnWords.value.length > 0) {
    transcript.value.push({
      text: currentTurnWords.value.join(' '),
      turn: currentTurnOrder.value,
      colorClass: colors[colorIndex].text,
    });
    currentTurnWords.value = [];
    currentTurnOrder.value = -1;
  }
};

watch(transcript, async () => {
  await nextTick();
  if (transcriptContainer.value) {
    transcriptContainer.value.scrollTop = transcriptContainer.value.scrollHeight;
  }
}, { deep: true });

watch(currentTurnWords, async () => {
  await nextTick();
  if (transcriptContainer.value) {
    transcriptContainer.value.scrollTop = transcriptContainer.value.scrollHeight;
  }
}, { deep: true });
</script>

<template>
  <div class="container mx-auto p-6 space-y-8 max-w-6xl">
    <!-- Header -->
    <div class="text-center space-y-2">
      <h1 class="text-4xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-emerald-600 bg-clip-text text-transparent">
        YouTube Transcript Streamer
      </h1>
      <p class="text-muted-foreground text-lg">Real-time transcript streaming with intelligent turn detection</p>
    </div>

    <!-- Search & Stream Panel -->
    <Card class="border-0 shadow-lg bg-gradient-to-br from-slate-50 to-white">
      <CardHeader class="pb-4">
        <CardTitle class="flex items-center gap-2">
          <Search class="h-5 w-5" />
          Search & Stream
        </CardTitle>
        <CardDescription>
          Find YouTube videos or paste a direct URL to start streaming transcripts
        </CardDescription>
      </CardHeader>
      <CardContent class="space-y-6">
        <!-- Search Section -->
        <div class="space-y-3">
          <div class="flex gap-3">
            <Input
              v-model="searchQuery"
              @keyup.enter="searchVideos"
              placeholder="Search YouTube videos..."
              class="flex-1 h-11"
            />
            <Button 
              @click="searchVideos" 
              :disabled="!searchQuery || isSearching"
              class="h-11 px-6"
            >
              <Loader2 v-if="isSearching" class="h-4 w-4 animate-spin mr-2" />
              <Search v-else class="h-4 w-4 mr-2" />
              Search
            </Button>
          </div>
        </div>

        <!-- Direct URL Section -->
        <div class="space-y-3">
          <Separator />
          <div class="flex gap-3">
            <Input
              v-model="streamingUrl"
              placeholder="Or paste YouTube video URL directly..."
              class="flex-1 h-11"
            />
            <Button
              @click="startStreaming(streamingUrl)"
              :disabled="!streamingUrl"
              variant="secondary"
              class="h-11 px-6"
            >
              <Play class="h-4 w-4 mr-2" />
              Stream
            </Button>
          </div>
        </div>

        <!-- Search Results -->
        <div v-if="searchResults.length > 0" class="space-y-4">
          <div class="flex items-center gap-2">
            <h3 class="text-lg font-semibold">Search Results</h3>
            <Badge variant="secondary">{{ searchResults.length }} found</Badge>
          </div>
          <ScrollArea class="h-64 w-full rounded-md border bg-white">
            <div class="p-4 space-y-3">
              <div
                v-for="(videoUrl, index) in searchResults"
                :key="videoUrl"
                class="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
              >
                <div class="flex items-center gap-3 flex-1 min-w-0">
                  <div class="flex-shrink-0 w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
                    <Play class="h-4 w-4 text-red-600" />
                  </div>
                  <a 
                    :href="videoUrl" 
                    target="_blank" 
                    class="text-sm text-foreground hover:text-primary truncate flex-1 flex items-center gap-1"
                  >
                    {{ videoUrl }}
                    <ExternalLink class="h-3 w-3 flex-shrink-0" />
                  </a>
                </div>
                <Button
                  @click="startStreaming(videoUrl)"
                  size="sm"
                  class="ml-4 flex-shrink-0"
                >
                  <Radio class="h-3 w-3 mr-1" />
                  Stream
                </Button>
              </div>
            </div>
          </ScrollArea>
        </div>

        <div v-else-if="searchQuery && searchResults.length === 0 && !isSearching" 
             class="text-center py-8 text-muted-foreground">
          <Search class="h-8 w-8 mx-auto mb-2 opacity-50" />
          No videos found for "{{ searchQuery }}"
        </div>
      </CardContent>
    </Card>

    <!-- Transcript Panel -->
    <Card class="border-0 shadow-lg bg-gradient-to-br from-slate-50 to-white">
      <CardHeader class="pb-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Radio class="h-5 w-5" />
            <CardTitle>Live Transcript</CardTitle>
            <Badge v-if="isStreaming" variant="default" class="animate-pulse">
              <div class="w-2 h-2 bg-green-400 rounded-full mr-1"></div>
              Live
            </Badge>
          </div>
        </div>
        <CardDescription v-if="streamingUrl" class="flex items-center gap-2">
          Streaming from: 
          <a :href="streamingUrl" target="_blank" class="text-primary hover:underline inline-flex items-center gap-1">
            <span class="truncate max-w-md">{{ streamingUrl }}</span>
            <ExternalLink class="h-3 w-3 flex-shrink-0" />
          </a>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea 
          ref="transcriptContainer"
          class="h-[500px] w-full rounded-lg border bg-white/50 backdrop-blur"
        >
          <div class="p-6 space-y-4">
            <!-- Empty State -->
            <div v-if="transcript.length === 0 && currentTurnWords.length === 0 && !streamingUrl" 
                 class="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <Radio class="h-12 w-12 mb-4 opacity-30" />
              <p class="text-lg font-medium">Ready to stream</p>
              <p class="text-sm">Select a video to start streaming its transcript</p>
            </div>

            <!-- Transcript Content -->
            <div class="space-y-4">
              <!-- Past turns -->
              <div
                v-for="(segment, index) in transcript"
                :key="index"
                class="p-4 rounded-lg border-l-4 bg-white/80 shadow-sm"
                :class="colors.find(c => c.text === segment.colorClass)?.bg || 'bg-gray-50 border-gray-200'"
              >
                <div class="flex items-start gap-3">
                  <Badge variant="outline" class="flex-shrink-0 mt-0.5">
                    Turn {{ segment.turn }}
                  </Badge>
                  <p :class="[segment.colorClass, 'text-base leading-relaxed flex-1']">
                    {{ segment.text }}
                  </p>
                </div>
              </div>

              <!-- Active turn -->
              <div
                v-if="currentTurnWords.length > 0"
                class="p-4 rounded-lg border-l-4 bg-white/80 shadow-sm animate-pulse"
                :class="colors[colorIndex]?.bg || 'bg-gray-50 border-gray-200'"
              >
                <div class="flex items-start gap-3">
                  <Badge variant="default" class="flex-shrink-0 mt-0.5 animate-pulse">
                    <div class="w-2 h-2 bg-current rounded-full mr-1 animate-ping"></div>
                    Turn {{ currentTurnOrder }}
                  </Badge>
                  <p :class="[colors[colorIndex]?.text || 'text-gray-600', 'text-base leading-relaxed flex-1 italic']">
                    {{ currentTurnWords.join(' ') }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  </div>
</template>

<style scoped>
.container {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  min-height: 100vh;
}

/* Custom scrollbar */
:deep(.scrollbar-thin) {
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
}

:deep(.scrollbar-thin::-webkit-scrollbar) {
  width: 6px;
}

:deep(.scrollbar-thin::-webkit-scrollbar-track) {
  background: #f1f5f9;
  border-radius: 3px;
}

:deep(.scrollbar-thin::-webkit-scrollbar-thumb) {
  background: #cbd5e1;
  border-radius: 3px;
}

:deep(.scrollbar-thin::-webkit-scrollbar-thumb:hover) {
  background: #94a3b8;
}
</style>