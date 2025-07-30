export type Word = {
	start: number;
	end: number;
	confidence: number;
	text: string;
	word_is_final: boolean;
}

export type TurnEventData = {
	type: 'Turn';
	turn_order: number;
	turn_is_formatted: boolean;
	end_of_turn: boolean;
	transcript: string;
	end_of_turn_confidence: number;
	words: Word[];
	
}

export type TranscriptSegment = {
	turn: number;
	colorClass: string;
	timestamp: number;
	confidence: number;
	text: string;
	words: Word[];
	translated_text?: string;
}

export type YoutubeInfo = {
	id: string;
	title: string;
	formats: any[]; // Or define a more specific 'Format' interface if needed
	thumbnails: Thumbnail[];
	description: string;
	channel_id: string;
	channel_url: string; // HttpUrl maps to string in TS
	duration: number;
	view_count: number;
	average_rating?: number | null; // tp.Optional[float] maps to number | null | undefined
	age_limit: number;
	webpage_url: string; // HttpUrl maps to string in TS
	categories: string[];
	tags: string[];
	playable_in_embed: boolean;
	live_status: string;
	media_type: string;
	release_timestamp?: number | null;
	_format_sort_fields: string[];
	automatic_captions?: { [key: string]: Caption[] } | null; // tp.Optional[dict[str,list[Caption]]]
	subtitles: any; // tp.Any maps to any in TS
	comment_count?: number | null;
	chapters?: Chapter[] | null;
	heatmap?: Heatmap[] | null;
	like_count: number;
	channel: string;
	channel_follower_count: number;
	channel_is_verified?: boolean | null;
	uploader: string;
	uploader_id: string;
	uploader_url: string; // HttpUrl maps to string in TS
	upload_date: string;
	timestamp: number;
	availability: string;
	original_url: string; // HttpUrl maps to string in TS
	webpage_url_basename: string;
	webpage_url_domain: string;
	extractor: string;
	extractor_key: string;
	playlist?: string | null;
	playlist_index?: string | null;
	display_id: string;
	fulltitle: string;
	duration_string: string;
	release_year?: any | null; // tp.Optional[tp.Any] maps to any | null | undefined
	is_live: boolean;
	was_live: boolean;
	requested_subtitles?: boolean | null;
	_has_drm?: boolean | null;
	epoch: number;
	asr: number;
	filesize: number;
	format_id: string;
	format_note: string;
	source_preference: number;
	fps?: number | null;
	audio_channels: number;
	heights?: number | null;
	quality: number;
	has_drm: boolean;
	tbr: number;
	filesize_approx: number;
	url: string; // HttpUrl maps to string in TS
	width?: number | null;
	language: string;
	language_preference: number;
	preference?: any | null; // tp.Optional[tp.Any] maps to any | null | undefined
	ext: string;
	vcodec: string;
	acodec: string;
	dynamic_range?: any | null; // tp.Optional[tp.Any] maps to any | null | undefined
	container: string;
	downloader_options: { [key: string]: any }; // dict[str,tp.Any] maps to {[key:string]: any}
	protocol: string;
	audio_ext: string;
	video_ext: string;
	vbr: number;
	abr: number;
	resolution: string;
	aspect_ratio?: number | null;
	http_headers: { [key: string]: string }; // dict[str,str] maps to {[key:string]: string}
	format: string;
}

export type Thumbnail = {
	url: string; // HttpUrl maps to string in TS
	preference: number;
	id: string;
	height?: number | null;
	width?: number | null;
}

export type Caption = {
	ext: string;
	url: string; // HttpUrl maps to string in TS
	name?: string | null;
	impersonate?: boolean | null;
}

export type Chapter = {
	start_time: number;
	title: string;
	end_time: number;
}

export type Heatmap = {
	start_time: number;
	end_time: number;
	value: number;
}