import typing as tp
from pydantic import BaseModel, Field, HttpUrl
from typing_extensions import TypedDict

class AutomaticCaptionsValue(BaseModel):
    ext:str
    url:HttpUrl
    name:str
    impersonate:tp.Optional[bool] = Field(default=None)
    __yt_dlp_client:str # type: ignore
        
class Fragment(TypedDict):
    url:HttpUrl
    duration:float

class Caption(BaseModel):
    ext: str
    url: HttpUrl
    name: tp.Optional[str] = Field(default=None)
    impersonate: tp.Optional[bool] = Field(default=None)

class Thumbnail(BaseModel):
    url:HttpUrl
    preference:int
    id:str
    height:tp.Optional[float] = Field(default=None)
    width:tp.Optional[float] = Field(default=None)
 
class Chapter(BaseModel):
    start_time:float
    title:str
    end_time:float
    
class Heatmap(BaseModel):
    start_time:float
    end_time:float
    value:float

class TranslationRequest(BaseModel):
    text: str
    language: str

class Format(BaseModel):
    ...
class YoutubeInfo(BaseModel):
    id:str
    title:str
    formats:list[Format]
    thumbnails:list[Thumbnail]
    description:str
    channel_id:str
    channel_url:HttpUrl
    duration:int
    view_count:int
    average_rating:tp.Optional[float] = Field(default=None)
    age_limit:int
    webpage_url:HttpUrl
    categories:list[str]
    tags:list[str]
    playable_in_embed:bool
    live_status:str
    media_type:str
    release_timestamp:tp.Optional[float]
    _format_sort_fields:list[str]
    automatic_captions:tp.Optional[dict[str,list[Caption]]] = Field(default=None)
    subtitles:tp.Any
    comment_count:tp.Optional[int] = Field(default=None)
    chapters:tp.Optional[list[Chapter]] = Field(default=None)
    heatmap:tp.Optional[list[Heatmap]] = Field(default=None)
    like_count:int
    channel:str
    channel_follower_count:int
    channel_is_verified:tp.Optional[bool] = Field(default=None)
    uploader:str
    uploader_id:str
    uploader_url:HttpUrl
    upload_date:str
    timestamp:int
    availability:str
    original_url:HttpUrl
    webpage_url_basename:str
    webpage_url_domain:str
    extractor:str
    extractor_key:str
    playlist:tp.Optional[str]
    playlist_index:tp.Optional[str]
    display_id:str
    fulltitle:str
    duration_string:str
    release_year:tp.Optional[tp.Any]
    is_live:bool
    was_live:bool
    requested_subtitles:tp.Optional[bool]
    _has_drm:tp.Optional[bool]
    epoch:int
    asr:int
    filesize:int
    format_id:str
    format_note:str
    source_preference:int
    fps:tp.Optional[int]
    audio_channels:int
    heights:tp.Optional[int] = Field(default=None)
    quality:float
    has_drm:bool
    tbr:float
    filesize_approx:int
    url:HttpUrl
    width:tp.Optional[int]
    language:str
    language_preference:int
    preference:tp.Optional[tp.Any]
    ext:str
    vcodec:str
    acodec:str
    dynamic_range:tp.Optional[tp.Any]
    container:str
    downloader_options:dict[str,tp.Any]
    protocol:str
    audio_ext:str
    video_ext:str
    vbr:int
    abr:float
    resolution:str
    aspect_ratio:tp.Optional[float] = Field(default=None)
    http_headers:dict[str,str]
    format:str