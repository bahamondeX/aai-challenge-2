<script setup lang="ts">
import type { TranscriptSegment, TurnEventData, YoutubeInfo } from '~/types'; // Assuming YoutubeInfo is now in your types
import {
  ExternalLink, Play, Search, Loader2, Radio, Languages,
  Volume2, Pause, Copy, Download, Settings, Zap,
  Eye, EyeOff, Trash2, Mic, Film // Added Film icon for video thumbnails
} from 'lucide-vue-next';
import { computed, ref, watch, nextTick } from 'vue'; // Explicitly import reactive functions

// Define a type for YouTube video search results, mapping directly from YoutubeInfo
// This interface can be moved to types.ts if it's used elsewhere
interface YoutubeSearchResult {
  id: string;
  title: string;
  description: string;
  thumbnailUrl: string;
  channelName: string; // Corresponds to 'channel' in YoutubeInfo
  viewCount: number;
  durationString: string; // Corresponds to 'duration_string'
  webpageUrl: string; // Corresponds to 'webpage_url'
}

const languages = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Spanish', flag: '🇪🇸' },
  { code: 'fr', name: 'French', flag: '🇫🇷' },
  { code: 'de', name: 'German', flag: '🇩🇪' },
  { code: 'it', name: 'Italian', flag: '🇮🇹' },
  { code: 'pt', name: 'Portuguese', flag: '🇵🇹' },
  { code: 'ru', name: 'Russian', flag: '🇷🇺' },
  { code: 'ja', name: 'Japanese', flag: '🇯🇵' },
  { code: 'ko', name: 'Korean', flag: '🇰🇷' },
  { code: 'zh', name: 'Chinese', flag: '🇨🇳' },
  { code: 'ar', name: 'Arabic', flag: '🇸🇦' },
  { code: 'hi', name: 'Hindi', flag: '🇮🇳' }
];
const colors = [
  { text: 'text-violet-700', bg: 'bg-gradient-to-r from-violet-50 to-purple-50 border-violet-200', accent: 'bg-violet-500' },
  { text: 'text-emerald-700', bg: 'bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-200', accent: 'bg-emerald-500' },
  { text: 'text-rose-700', bg: 'bg-gradient-to-r from-rose-50 to-pink-50 border-rose-200', accent: 'bg-rose-500' },
  { text: 'text-blue-700', bg: 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200', accent: 'bg-blue-500' },
  { text: 'text-amber-700', bg: 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200', accent: 'bg-amber-500' },
  { text: 'text-cyan-700', bg: 'bg-gradient-to-r from-cyan-50 to-sky-50 border-cyan-200', accent: 'bg-cyan-500' }
];
let colorIndex = 0;

const searchQuery = ref<string>('');
const searchResults = ref<YoutubeSearchResult[]>([]);
const streamingUrl = ref<string>('');
const transcript = ref<TranscriptSegment[]>([]);
const eventSource = ref<EventSource | null>(null);
const currentTurnWords = ref<string[]>([]);
const currentTurnOrder = ref<number>(-1);
const transcriptContainer = ref<HTMLElement | null>(null);
const isSearching = ref(false);
const searchEventSource = ref<EventSource | null>(null); // New EventSource for search
const isStreaming = ref(false);
const isPaused = ref(false);
const autoScroll = ref(true);
const showConfidence = ref(false);
const language = ref<string>('es');

const selectedLanguage = computed(() =>
  languages.find(l => l.code === language.value) || languages[1]
);
const transcriptStats = computed(() => ({
  totalWords: transcript.value.reduce((acc, segment) => acc + segment.text.split(' ').length, 0) + currentTurnWords.value.length,
  totalTurns: transcript.value.length + (currentTurnWords.value.length > 0 ? 1 : 0),
  avgConfidence: transcript.value.length > 0
    ? Math.round(transcript.value.reduce((acc, segment) => acc + segment.confidence, 0) / transcript.value.length * 100)
    : 0
}));

/**
 * Starts streaming the transcript from a given YouTube video URL.
 * @param url The YouTube video URL.
 */
function startStreaming(url: string, language: string): void {
  // Close any existing transcript stream
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
  isPaused.value = false;
  const params = new URLSearchParams({
    url,
    language
  });

  eventSource.value = new EventSource(`/api/transcribe?${params.toString()}`);
  eventSource.value.onmessage = async (event: MessageEvent) => {
    if (isPaused.value) return;
    try {
      const data: TurnEventData = JSON.parse(event.data);
      if (data.type === 'Turn') {
        await handleTurnEvent(data);
      }
    } catch (e) {
      console.error('Error parsing SSE data for transcript:', e, event.data);
    }
  };
  eventSource.value.onerror = (error: Event) => {
    transcriptContainer.value?.classList.add('border-red-500');
    console.error('Transcript EventSource failed:', error);
    eventSource.value?.close();
    eventSource.value = null;
    isStreaming.value = false;
  };
  eventSource.value.onopen = () => {
    transcriptContainer.value?.classList.remove('animate-transcribing');
  };
};

/**
 * Stops the current streaming session.
 */
function stopStreaming(): void {
  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }
  isStreaming.value = false;
  isPaused.value = false;
};

/**
 * Toggles the pause state of the streaming.
 */
function togglePause(): void {
  isPaused.value = !isPaused.value;
};

/**
 * Clears the entire transcript.
 */
function clearTranscript(): void {
  transcript.value = [];
  currentTurnWords.value = [];
  currentTurnOrder.value = -1;
  colorIndex = 0;
  streamingUrl.value = '';
};

/**
 * Downloads the transcript as a plain text file.
 */
function downloadTranscript(): void {
  const fullText = transcript.value.map(segment =>
    `[${new Date(segment.timestamp).toLocaleTimeString()}] Turn ${segment.turn} (${Math.round(segment.confidence * 100)}% confidence): ${segment.text}`
    + (segment.translated_text ? `\n   Translated: ${segment.translated_text}` : '')
  ).join('\n\n');

  const blob = new Blob([fullText], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `transcript-${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
};

/**
 * Searches for YouTube videos based on the searchQuery using EventSource.
 */
async function searchVideos(): Promise<void> {
  if (!searchQuery.value) return;

  // Close any existing search stream
  if (searchEventSource.value) {
    searchEventSource.value.close();
    searchEventSource.value = null;
  }

  searchResults.value = []; // Clear previous search results
  isSearching.value = true;

  const params = new URLSearchParams({
    query: searchQuery.value
  });

  searchEventSource.value = new EventSource(`/api/search?${params.toString()}`);

  searchEventSource.value.onmessage = (event: MessageEvent) => {
    try {
      const videoInfo: YoutubeInfo = JSON.parse(event.data);
      // Map YoutubeInfo to YoutubeSearchResult
      const mappedVideo: YoutubeSearchResult = {
        id: videoInfo.id,
        title: videoInfo.title,
        description: videoInfo.description,
        thumbnailUrl: videoInfo.thumbnails.sort((a, b) => (b.preference || 0) - (a.preference || 0) || (b.width || 0) - (a.width || 0))[0]?.url || '',
        channelName: videoInfo.channel,
        viewCount: videoInfo.view_count,
        durationString: videoInfo.duration_string,
        webpageUrl: videoInfo.webpage_url
      };
      searchResults.value.push(mappedVideo);
    } catch (e) {
      console.error('Error parsing SSE data for search result:', e, event.data);
    }
  };

  searchEventSource.value.onerror = (error: Event) => {
    console.error('Search EventSource failed:', error);
    searchEventSource.value?.close();
    searchEventSource.value = null;
    isSearching.value = false; // Stop loading indicator on error
  };

  searchEventSource.value.onopen = () => {
    // console.log('Search EventSource opened.');
  };

  // There's no explicit 'end' event for SSE, so we assume it completes when
  // the 'onmessage' or 'onerror' handlers indicate no more data or an error.
  // For user experience, you might want a timeout or a specific "end" message
  // from the server if it explicitly closes the connection.
  // For now, we rely on onerror or the browser closing the connection to stop isSearching.
};

/**
 * Copies the entire transcript text to the clipboard.
 */
async function copyTranscript(): Promise<void> {
  let fullText = transcript.value.map(segment =>
    `Turn ${segment.turn}: ${segment.text}`
    + (segment.translated_text ? `\n   Translated: ${segment.translated_text}` : '')
  ).join('\n\n');

  if (currentTurnWords.value.length > 0) {
    fullText += `\n\nTurn ${currentTurnOrder.value}: ${currentTurnWords.value.join(' ')}`;
  }

  await navigator.clipboard.writeText(fullText);
};

/**
 * Handles incoming 'Turn' events from the EventSource.
 * Processes words and updates the transcript.
 * @param data The TurnEventData received from the stream.
 */
async function handleTurnEvent(data: TurnEventData): Promise<void> {
  const newWords = data.words || [];
  const avgConfidence = newWords.length > 0
    ? newWords.reduce((acc, word) => acc + word.confidence, 0) / newWords.length
    : 0;
  if (data.turn_order !== currentTurnOrder.value) {
    if (currentTurnWords.value.length > 0) {
      const currentSegmentText = currentTurnWords.value.join(' ');
      let translatedTextForSegment: string | undefined = undefined;

      if (language.value !== 'en') {
        translatedTextForSegment = await translate(currentSegmentText);
      }

      transcript.value.push({
        text: currentSegmentText,
        turn: currentTurnOrder.value,
        colorClass: colors[(colorIndex - 1 + colors.length) % colors.length].text,
        timestamp: Date.now(),
        confidence: avgConfidence,
        words: [],
        translated_text: translatedTextForSegment
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
    const finalTurnText = currentTurnWords.value.join(' ');
    let translatedTextForFinalTurn: string | undefined = undefined;

    if (language.value !== 'en') {
      translatedTextForFinalTurn = await translate(finalTurnText);
    }

    transcript.value.push({
      text: finalTurnText,
      turn: currentTurnOrder.value,
      colorClass: colors[colorIndex].text,
      timestamp: Date.now(),
      confidence: avgConfidence,
      words: newWords,
      translated_text: translatedTextForFinalTurn
    });
    currentTurnWords.value = [];
    currentTurnOrder.value = -1;
  }
};


async function translate(text: string): Promise<string> {
  try {
    const response = await fetch('/api/translate', {
      method: 'POST',
      body: JSON.stringify({ text, language: language.value }),
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (!response.ok) {
      throw new Error(`Translation failed with status: ${response.status}`);
    }
    const translatedText = await response.text();
    return translatedText;
  } catch (error) {
    console.error('Error during translation:', error);
    return `Translation Error: ${text}`;
  }
};
// Watcher for transcript changes to enable auto-scrolling
watch(transcript, async () => {
  if (autoScroll.value) {
    await nextTick();
    if (transcriptContainer.value) {
      transcriptContainer.value.scrollTop = transcriptContainer.value.scrollHeight;
    }
  }
}, { deep: true });

// Watcher for currentTurnWords changes to enable auto-scrolling
watch(currentTurnWords, async () => {
  if (autoScroll.value) {
    await nextTick();
    if (transcriptContainer.value) {
      transcriptContainer.value.scrollTop = transcriptContainer.value.scrollHeight;
    }
  }
}, { deep: true });

</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/30">
    <div class="container mx-auto p-6 space-y-8 max-w-7xl">
      <div class="text-center space-y-4 py-8">
        <div class="relative">
          <h1 class="text-6xl font-black bg-gradient-to-r from-violet-600 via-blue-600 to-emerald-600 bg-clip-text text-transparent animate-gradient-x">
            YouTube Transcript Streamer
          </h1>
          <div class="absolute -top-2 -right-2 w-4 h-4 bg-green-400 rounded-full animate-pulse shadow-lg shadow-green-400/50"></div>
        </div>
        <p class="text-muted-foreground text-xl max-w-2xl mx-auto leading-relaxed">
          Real-time transcript streaming with AI-powered translation and intelligent turn detection
        </p>

        <div v-if="isStreaming" class="flex items-center justify-center gap-8 mt-6">
          <div class="flex items-center gap-2 px-4 py-2 bg-white/80 backdrop-blur rounded-full border shadow-sm">
            <Mic class="h-4 w-4 text-blue-600" />
            <span class="text-sm font-medium">{{ transcriptStats.totalTurns }} turns</span>
          </div>
          <div class="flex items-center gap-2 px-4 py-2 bg-white/80 backdrop-blur rounded-full border shadow-sm">
            <Zap class="h-4 w-4 text-emerald-600" />
            <span class="text-sm font-medium">{{ transcriptStats.totalWords }} words</span>
          </div>
          <div class="flex items-center gap-2 px-4 py-2 bg-white/80 backdrop-blur rounded-full border shadow-sm">
            <Volume2 class="h-4 w-4 text-amber-600" />
            <span class="text-sm font-medium">{{ transcriptStats.avgConfidence }}% accuracy</span>
          </div>
        </div>
      </div>

      <Card class="border-0 shadow-2xl bg-white/90 backdrop-blur-sm">
        <CardHeader class="pb-6">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-gradient-to-r from-violet-500 to-blue-500 rounded-xl">
                <Search class="h-6 w-6 text-white" />
              </div>
              <div>
                <CardTitle class="text-2xl">Control Center</CardTitle>
                <CardDescription class="text-base">
                  Search, stream, and configure your transcript experience
                </CardDescription>
              </div>
            </div>

            <div class="flex items-center gap-3">
              <Languages class="h-5 w-5 text-muted-foreground" />
              <Select v-model="language">
                <SelectTrigger class="w-[200px] h-10">
                  <SelectValue class="flex items-center gap-2">
                    <span v-if="selectedLanguage">{{ selectedLanguage.flag }} {{ selectedLanguage.name }}</span>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="lang in languages" :key="lang.code" :value="lang.code">
                    <div class="flex items-center gap-2">
                      <span>{{ lang.flag }}</span>
                      <span>{{ lang.name }}</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>

        <CardContent class="space-y-8">
          <div class="space-y-4">
            <h3 class="text-lg font-semibold flex items-center gap-2">
              <Search class="h-5 w-5 text-violet-600" />
              Search YouTube
            </h3>
            <div class="flex gap-3">
              <Input
                v-model="searchQuery"
                @keyup.enter="searchVideos"
                placeholder="Search for YouTube videos..."
                class="flex-1 h-12 text-base border-2 focus:border-violet-500 transition-colors"
              />
              <Button
                @click="searchVideos"
                :disabled="!searchQuery || isSearching"
                class="h-12 px-8 bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-700 hover:to-blue-700 cursor-pointer"
              >
                <Loader2 v-if="isSearching" class="h-5 w-5 animate-spin mr-2" />
                <Search v-else class="h-5 w-5 mr-2" />
                {{ isSearching ? 'Searching...' : 'Search' }}
              </Button>
            </div>
             <div v-if="isSearching" class="text-sm text-muted-foreground flex items-center gap-2 mt-2">
                <Loader2 class="h-4 w-4 animate-spin" />
                Streaming search results...
            </div>
          </div>

          <div class="space-y-4">
            <Separator class="my-6" />
            <h3 class="text-lg font-semibold flex items-center gap-2">
              <Play class="h-5 w-5 text-emerald-600" />
              Direct Stream
            </h3>
            <div class="flex gap-3">
              <Input
                v-model="streamingUrl"
                placeholder="Paste YouTube video URL here..."
                class="flex-1 h-12 text-base border-2 focus:border-emerald-500 transition-colors"
              />
              <Button
                @click="startStreaming(streamingUrl, language)"
                :disabled="!streamingUrl"
                variant="secondary"
                class="h-12 px-8 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white cursor-pointer"
              >
                <Play class="h-5 w-5 mr-2" />
                Stream
              </Button>
            </div>
          </div>

          <div v-if="searchResults.length > 0 || isSearching" class="space-y-4">
            <div class="flex items-center gap-3">
              <h3 class="text-lg font-semibold">Search Results</h3>
              <Badge variant="secondary" class="text-sm px-3 py-1">{{ searchResults.length }} found</Badge>
            </div>
            <ScrollArea class="h-80 w-full rounded-xl border-2 bg-white">
              <div class="p-6 space-y-4">
                <div
                  v-for="video in searchResults"
                  :key="video.id"
                  class="group flex items-center justify-between p-4 rounded-xl border-2 bg-gradient-to-r from-white to-slate-50 hover:from-violet-50 hover:to-blue-50 hover:border-violet-200 transition-all duration-300 hover:shadow-lg"
                >
                  <div class="flex items-center gap-4 flex-1 min-w-0">
                    <img v-if="video.thumbnailUrl" :src="video.thumbnailUrl" alt="Video Thumbnail" class="w-16 h-12 object-cover rounded-md flex-shrink-0" />
                    <div v-else class="w-16 h-12 bg-gray-200 rounded-md flex items-center justify-center flex-shrink-0">
                      <Film class="h-6 w-6 text-gray-400" />
                    </div>

                    <div class="flex-1 min-w-0">
                      <a
                        :href="video.webpageUrl"
                        target="_blank"
                        class="text-foreground hover:text-violet-600 truncate flex-1 flex items-center gap-2 font-medium group-hover:text-violet-700 transition-colors"
                      >
                        <span class="truncate max-w-[250px]">{{ video.title }}</span>
                        <ExternalLink class="h-4 w-4 flex-shrink-0 opacity-60" />
                      </a>
                      <p class="text-sm text-muted-foreground truncate">{{ video.channelName }} &bull; {{ video.durationString }}</p>
                      <p class="text-xs text-muted-foreground truncate">Views: {{ video.viewCount.toLocaleString() }}</p>
                    </div>
                  </div>
                  <Button
                    @click="startStreaming(video.webpageUrl, language)"
                    size="sm"
                    class="ml-4 flex-shrink-0 bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-700 hover:to-blue-700 cursor-pointer"
                  >
                    <Radio class="h-4 w-4 mr-2" />
                    Stream
                  </Button>
                </div>
                <div v-if="isSearching && searchResults.length === 0" class="text-center py-4 text-muted-foreground">
                    <Loader2 class="h-8 w-8 mx-auto mb-2 animate-spin" />
                    <p>Loading search results...</p>
                </div>
              </div>
            </ScrollArea>
          </div>

          <div v-else-if="searchQuery && searchResults.length === 0 && !isSearching"
               class="text-center py-12 text-muted-foreground">
            <Search class="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p class="text-lg font-medium">No videos found</p>
            <p class="text-sm">Try a different search term</p>
          </div>
        </CardContent>
      </Card>

      <Card class="border-0 shadow-2xl bg-white/90 backdrop-blur-sm">
        <CardHeader class="pb-6">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-gradient-to-r from-emerald-500 to-teal-500 rounded-xl">
                <Radio class="h-6 w-6 text-white" />
              </div>
              <div>
                <CardTitle class="text-2xl">Live Transcript</CardTitle>
                <CardDescription v-if="streamingUrl" class="flex items-center gap-2 text-base">
                  Streaming from:
                  <a :href="streamingUrl" target="_blank" class="text-primary hover:underline inline-flex items-center gap-1 font-medium">
                    <span class="truncate max-w-md">{{ streamingUrl }}</span>
                    <ExternalLink class="h-3 w-3 flex-shrink-0" />
                  </a>
                </CardDescription>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <Button
                v-if="isStreaming"
                @click="togglePause"
                variant="outline"
                size="sm"
                class="h-10 cursor-pointer"
              >
                <Pause v-if="!isPaused" class="h-4 w-4 mr-2" />
                <Play v-else class="h-4 w-4 mr-2" />
                {{ isPaused ? 'Resume' : 'Pause' }}
              </Button>

              <Button
                @click="autoScroll = !autoScroll"
                variant="outline"
                size="sm"
                :class="autoScroll ? 'bg-green-50 border-green-200' : ''"
                class="h-10 cursor-pointer"
              >
                <Eye v-if="autoScroll" class="h-4 w-4 mr-2" />
                <EyeOff v-else class="h-4 w-4 mr-2" />
                Auto-scroll
              </Button>

              <Button
                @click="showConfidence = !showConfidence"
                variant="outline"
                size="sm"
                :class="showConfidence ? 'bg-blue-50 border-blue-200' : ''"
                class="h-10 cursor-pointer"
              >
                <Settings class="h-4 w-4 mr-2" />
                Confidence
              </Button>

              <Button
                @click="copyTranscript"
                variant="outline"
                size="sm"
                class="h-10 cursor-pointer"
                :disabled="transcript.length === 0"
              >
                <Copy class="h-4 w-4 mr-2" />
                Copy
              </Button>

              <Button
                @click="downloadTranscript"
                variant="outline"
                size="sm"
                class="h-10 cursor-pointer"
                :disabled="transcript.length === 0"
              >
                <Download class="h-4 w-4 mr-2" />
                Download
              </Button>

              <Button
                @click="clearTranscript"
                variant="outline"
                size="sm"
                class="h-10 text-red-600 hover:bg-red-50 cursor-pointer"
                :disabled="transcript.length === 0"
              >
                <Trash2 class="h-4 w-4 mr-2" />
                Clear
              </Button>

              <Button
                v-if="isStreaming"
                @click="stopStreaming"
                variant="destructive"
                size="sm"
                class="h-10 cursor-pointer"
              >
                Stop
              </Button>
            </div>
          </div>

          <div class="flex items-center gap-4 mt-4">
            <Badge v-if="isStreaming && !isPaused" variant="default" class="animate-pulse bg-green-500">
              <div class="w-2 h-2 bg-white rounded-full mr-2 animate-ping"></div>
              Streaming Live {{ streamingUrl }}
            </Badge>
            <Badge v-else-if="isPaused" variant="secondary" class="bg-yellow-100 text-yellow-800">
              <Pause class="w-3 h-3 mr-1" />
              Paused
            </Badge>
            <Badge v-if="selectedLanguage" variant="outline" class="bg-blue-50">
              {{ selectedLanguage.flag }} Translating to {{ selectedLanguage.name }}
            </Badge>
          </div>
        </CardHeader>

        <CardContent>
          <ScrollArea
            ref="transcriptContainer"
            class="h-[600px] w-full rounded-2xl border-2 bg-gradient-to-br from-white via-slate-50/50 to-blue-50/30 backdrop-blur"
          >
            <div class="p-8 space-y-6">
              <div v-if="transcript.length === 0 && currentTurnWords.length === 0 && !streamingUrl"
                   class="flex flex-col items-center justify-center h-96 text-muted-foreground">
                <div class="relative mb-6">
                  <Radio class="h-16 w-16 opacity-20" />
                  <div class="absolute -top-1 -right-1 w-6 h-6 bg-gradient-to-r from-violet-500 to-blue-500 rounded-full flex items-center justify-center">
                    <Zap class="h-3 w-3 text-white" />
                  </div>
                </div>
                <p class="text-2xl font-bold mb-2">Ready to Stream</p>
                <p class="text-lg">Select a video to start streaming its transcript</p>
              </div>

              <div class="space-y-6">
                <div
                  v-for="(segment, index) in transcript"
                  :key="index"
                  class="group relative p-6 rounded-2xl border-l-4 shadow-sm hover:shadow-md transition-all duration-300"
                  :class="colors.find(c => c.text === segment.colorClass)?.bg || 'bg-gray-50 border-gray-200'"
                >
                  <div class="flex items-start gap-4">
                    <div class="flex flex-col items-center gap-2">
                      <Badge variant="outline" class="flex-shrink-0 font-medium">
                        Turn {{ segment.turn }}
                      </Badge>
                      <div
                        class="w-3 h-3 rounded-full"
                        :class="colors.find(c => c.text === segment.colorClass)?.accent || 'bg-gray-400'"
                      ></div>
                    </div>
                    <div class="flex-1 space-y-2">
                      <p :class="[segment.colorClass, 'text-lg leading-relaxed font-medium']">
                        {{ segment.text }}
                      </p>
                      <p v-if="segment.translated_text" class="text-sm text-muted-foreground italic mt-1">
                        {{ segment.translated_text }}
                      </p>
                      <div v-if="showConfidence" class="flex items-center gap-4 text-sm text-muted-foreground">
                        <span class="flex items-center gap-1">
                          <Volume2 class="h-3 w-3" />
                          {{ Math.round(segment.confidence * 100) }}% confidence
                        </span>
                        <span>{{ new Date(segment.timestamp).toLocaleTimeString() }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  v-if="currentTurnWords.length > 0"
                  class="relative p-6 rounded-2xl border-l-4 shadow-lg animate-pulse-subtle"
                  :class="colors[colorIndex]?.bg || 'bg-gray-50 border-gray-200'"
                >
                  <div class="flex items-start gap-4">
                    <div class="flex flex-col items-center gap-2">
                      <Badge variant="default" class="flex-shrink-0 animate-pulse bg-gradient-to-r from-violet-600 to-blue-600">
                        <div class="w-2 h-2 bg-white rounded-full mr-2 animate-ping"></div>
                        Turn {{ currentTurnOrder }}
                      </Badge>
                      <div class="w-3 h-3 rounded-full bg-gradient-to-r from-violet-500 to-blue-500 animate-pulse"></div>
                    </div>
                    <div class="flex-1">
                      <p :class="[colors[colorIndex]?.text || 'text-gray-600', 'text-lg leading-relaxed font-medium italic']">
                        {{ currentTurnWords.join(' ') }}
                        <span class="inline-block w-2 h-5 bg-current ml-1 animate-pulse"></span>
                      </p>
                    </div>
                  </div>

                  <div class="absolute top-2 right-2">
                    <div class="flex items-center gap-1 px-2 py-1 bg-green-500 text-white text-xs rounded-full animate-pulse">
                      <div class="w-1.5 h-1.5 bg-white rounded-full animate-ping"></div>
                      LIVE
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.container {
  background: linear-gradient(135deg, #f8fafc 0%, #e0f2fe 25%, #e8f5e8 50%, #f3e8ff 75%, #fef7cd 100%);
  background-size: 400% 400%;
  animation: gradientShift 20s ease infinite;
}

@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  25% { background-position: 100% 25%; }
  50% { background-position: 100% 100%; }
  75% { background-position: 0% 75%; }
  100% { background-position: 0% 50%; }
}

@keyframes animate-gradient-x {
  0%, 100% {
    background-size: 200% 200%;
    background-position: left center;
  }
  50% {
    background-size: 200% 200%;
    background-position: right center;
  }
}

.animate-gradient-x {
  animation: animate-gradient-x 4s ease infinite;
}

@keyframes animate-pulse-subtle {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.95;
    transform: scale(1.002);
  }
}

.animate-pulse-subtle {
  animation: animate-pulse-subtle 2s ease-in-out infinite;
}

/* Glass morphism effects */
.bg-white\/90 {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

/* Enhanced scrollbar */
:deep(.scrollbar-thin) {
  scrollbar-width: thin;
  scrollbar-color: #8b5cf6 #f1f5f9;
}

:deep(.scrollbar-thin::-webkit-scrollbar) {
  width: 8px;
}

:deep(.scrollbar-thin::-webkit-scrollbar-track) {
  background: rgba(241, 245, 249, 0.5);
  border-radius: 10px;
  backdrop-filter: blur(10px);
}

:deep(.scrollbar-thin::-webkit-scrollbar-thumb) {
  background: linear-gradient(135deg, #8b5cf6, #3b82f6);
  border-radius: 10px;
  border: 2px solid rgba(255, 255, 255, 0.2);
}

:deep(.scrollbar-thin::-webkit-scrollbar-thumb:hover) {
  background: linear-gradient(135deg, #7c3aed, #2563eb);
}

/* Hover effects for cards */
.group:hover .group-hover\:scale-105 {
  transform: scale(1.05);
}

.group:hover .group-hover\:shadow-lg {
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}

/* Custom focus styles */
:deep(.focus\:border-violet-500:focus) {
  border-color: #8b5cf6;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
}

:deep(.focus\:border-emerald-500:focus) {
  border-color: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
}

/* Animated background for streaming status */
@keyframes pulse-ring {
  0% {
    transform: scale(0.33);
  }
  40%, 50% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: scale(1.33);
  }
}

.animate-pulse-ring {
  animation: pulse-ring 1.25s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
}

/* Floating animation for icons */
@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-10px);
  }
}

.animate-float {
  animation: float 6s ease-in-out infinite;
}

/* Shimmer effect for loading states */
@keyframes shimmer {
  0% {
    background-position: -468px 0;
  }
  100% {
    background-position: 468px 0;
  }
}

.animate-shimmer {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 400% 100%;
  animation: shimmer 1.2s ease-in-out infinite;
}

/* Glow effects */
.glow-violet {
  box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
}

.glow-emerald {
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);
}

.glow-blue {
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
}

/* Typography enhancements */
.text-gradient {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Button hover states */
:deep(.btn-gradient:hover) {
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}

/* Card entrance animations */
@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translate3d(0, 40px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

.animate-slide-in-up {
  animation: slideInUp 0.6s ease-out;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .text-6xl {
    font-size: 3rem;
  }
  
  .container {
    padding: 1rem;
  }
  
  .space-y-8 > :not([hidden]) ~ :not([hidden]) {
    margin-top: 1.5rem;
  }
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .bg-white\/90 {
    background: rgba(15, 23, 42, 0.9);
    color: white;
  }
  
  :deep(.scrollbar-thin::-webkit-scrollbar-track) {
    background: rgba(15, 23, 42, 0.5);
  }
}

/* High contrast mode */
@media (prefers-contrast: high) {
  .bg-gradient-to-r {
    background: #000;
    color: #fff;
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-delay: -1ms !important;
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    background-attachment: initial !important;
    scroll-behavior: auto !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
  }
}

/* Print styles */
@media print {
  .container {
    background: white !important;
  }
  
  .bg-gradient-to-r,
  .bg-gradient-to-br {
    background: white !important;
    color: black !important;
  }
  
  .shadow-lg,
  .shadow-2xl {
    box-shadow: none !important;
  }
}

.animate-transcribing {
  animation: transcribing 1s ease-in-out infinite;
}

@keyframes transcribing {
  0% {
    border-color: #8b5cf6;
  }
  50% {
    border-color: #3b82f6;
  }
}


</style>
