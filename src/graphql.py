"""GraphQL client for search-api.artlist.io."""
from typing import Any
from . import config
from . import auth
from .http_client import post_json, HttpError
import logging

log = logging.getLogger(__name__)

# Persist the GraphQL queries verbatim from the HARs to maximize compatibility.
# (Artlist may add server-side field validation; reusing exact queries reduces risk.)

QUERIES = {
    "RootCategories": """
query RootCategories($assetType: String!) {
    rootCategories(assetType: $assetType) {
      id
      name
      nameForUrl
      subCategory {
        id
        name
        nameForUrl
        subCategory {
          id
          name
          nameForUrl
        }
      }
    }
  }
""",
    "searchTermsAutosuggestions": """
    query trendingSearchTerm(
    $assetType: SearchTermsAutosuggestionsSupportedAssetType!
    ) {
    searchTermsAutosuggestions(assetType: $assetType) {
        terms
    }
    }
""",
    "Catalog": """
query Catalog($page: Int, $take: Int) {
  catalog(page: $page, take: $take) {
    platformCode,
    results {
      slug,
      name,
      countryCode
      fromDate
      toDate
    }
  }
}
""",
    "ClipList": """
query ClipList($filterCategories: [Int!], $searchTerms: [String], $sortType: Int, $queryType: Int, $page: Int, $durationMin: Int, $durationMax: Int, $orientation: ClipOrientation, $frameRate: ClipFPS, $includeAIContent: Boolean) {
  clipList(filterCategories: $filterCategories, searchTerms: $searchTerms, sortType: $sortType, queryType: $queryType, page: $page, durationMin: $durationMin, durationMax: $durationMax, orientation: $orientation, frameRate: $frameRate, includeAIContent: $includeAIContent) {
    isGeoSearch
    querySearchType
    exactResults {
      id
      clipName
      clipNameForUrl
      thumbnailUrl
      clipPath
      isInFavorites
      isInDownloadHistory
      isNew
      isVfx
      isInFolder
      filmMakerDisplayName
      storyId
      storyNameForURL
      isLicensed
      isOriginal
      storyName
      duration
      width
      height
      orientation
      isMadeWithAi
      geoLocationGridDisplay
      aiFrames {
        thumbnailUrl
        timestampSec
      }
      availableFormats {
        id
        displayName
      }
      filmMakerId
      filmMakerNameForUrl
    }
    similarResults {
      id
      clipName
      clipNameForUrl
      thumbnailUrl
      clipPath
      isInFavorites
      isInDownloadHistory
      isNew
      isVfx
      isInFolder
      filmMakerDisplayName
      storyId
      storyNameForURL
      isLicensed
      isOriginal
      storyName
      duration
      width
      height
      orientation
      isMadeWithAi
      geoLocationGridDisplay
      aiFrames {
        thumbnailUrl
        timestampSec
      }
    }
    totalExact
    totalSimilar
    topDownloadedClipsCount
    totalLexicalResults
    totalSemanticResults
  }
}
""",
    "TemplateRootCategories": """
query TemplateRootCategories {
  templateRootCategories {
    name
    id
    uniqueId
  }
}
""",
    "templateSearchFilters": """
query TemplateRootCategories {
  templateSearchFilters {
    softwareNames {
      id
      name
    }
    resolutions {
      id
      name
    }
    aspectRatios {
      id
      name
    }
    softwareVersions {
      id
      name
    }
  }
}
""",
    "TemplatesList": """
query TemplatesList($payload: TemplatesListSearchRequest!) {
  templatesList(payload: $payload) {
    id
    name
    artistId
    artistName
    artistNameForUrl
    isNew
    thumbnailUrl
    previewVideoFileUrl
    files {
      softwareName
      softwareVersionName
    },
    availableFormats {
      id
      displayName
    },
    nameForUrl
    resolutions
    isOriginal
  }
}
""",
    "Luts": """
  query Luts(
    $lutBasePreviewId: String!
    $saturation: [String!]
    $temperature: [String!]
    $contrast: [String!]
    $videoCategoryName: [String!]
    $moodCategoryName: [String!]
    $page: Float
    $take: Float
  ) {
    luts(
      lutBasePreviewId: $lutBasePreviewId
      contrast: $contrast
      saturation: $saturation
      temperature: $temperature
      videoCategoryName: $videoCategoryName
      moodCategoryName: $moodCategoryName
      page: $page
      take: $take
    ) {
      id
      name
      thumbnailUrl
      hlsUrl
      videoCategoryName
      moodCategoryName
      contrast
      saturation
      temperature
    }
  }
""",
    "LutsByIds": """
query LutsByIds($ids: [String!]!) {
  lutsByIds(ids: $ids) {
    id
    name
    videoCategoryName
    moodCategoryName
    contrast
    saturation
    temperature
    files {
      hlsUrl
      thumbnailUrl
      lutBasePreviewId
    }
  }
}
""",
    "SongList": """
  query SongList($page: Int!, $songSortType: SongSortType!, $take: Int!, $vocalType: VocalType!, $bpmMax: Int, $bpmMin: Int, $durationMax: Int, $durationMin: Int, $excludedCategoryIds: [Int], $categoryIds: [Int], $searchTerm: String, $isWithStemsOnly: Boolean, $excludedSongIds: [String]) {
    songList(page: $page, songSortType: $songSortType, take: $take, vocalType: $vocalType, bpmMax: $bpmMax, bpmMin: $bpmMin, durationMax: $durationMax, durationMin: $durationMin, excludedCategoryIds: $excludedCategoryIds, categoryIds: $categoryIds, searchTerm: $searchTerm, isWithStemsOnly: $isWithStemsOnly, excludedSongIds: $excludedSongIds){
      songs {
        albumThumbFilePath
        albumImageFilePath
        albumId
        albumName
        albumNameForURL
        artistId
        artistName
        duration
        durationTime
        explicit
        featuredArtists
        isOriginal
        isNew
        lyrics
        nameForURL
        originalVersionID
        primaryArtists
        assetTypeId
        sitePlayableFilePath
        songName
        songId
        waveSurferFilePath
        numberOfStems
        isPreRelease
        officialReleaseDate
        genreCategories {
          id
          name
          parentName
        }
        hook30End
        hook30Start
        versions {
          albumThumbFilePath
          albumImageFilePath
          albumId
          albumName
          albumNameForURL
          artistId
          artistName
          duration
          durationTime
          explicit
          featuredArtists
          isOriginal
          isNew
          lyrics
          nameForURL
          originalVersionID
          primaryArtists
          assetTypeId
          sitePlayableFilePath
          songName
          songId
          waveSurferFilePath
          numberOfStems
          isPreRelease
          officialReleaseDate
          genreCategories {
            id
            name
            parentName
          }
          hook30End
          hook30Start
        }
      }
      totalResults
    }
  }
""",
    "SfxList": """
query SfxList($categoryIds: String!, $page: Float!, $tags: String!, $term: String!, $sortBy: SfxListRequestSortByOptions!) {
  sfxList(categoryIds: $categoryIds, page: $page, tags: $tags, term: $term, sortBy: $sortBy) {
    page
    songs {
      albumId
      albumImageFilePath
      albumName
      albumNameForURL
      artistId
      artistName
      assetTypeId
      durationTime
      grandChildCategories {
        id
        name
        parentName
      }
      isNew
      nameForURL
      sitePlayableFilePath
      songId
      songName
      waveSurferFilePath
    }
    suggestion {
      displayOrder
      id
      name
    }
  }
}
""",
}


def _run(query_key: str, variables: dict, version: int = 2) -> dict:
    """Run a GraphQL query. version=1 uses /v1/graphql, version=2 uses /v2/graphql."""
    url = config.HOST_SEARCH_API_V1 if version == 1 else config.HOST_SEARCH_API_V2
    body = {
        "query": QUERIES[query_key],
        "variables": variables,
    }
    try:
        resp = post_json(url, body, headers=auth.jwt_headers())
        if "errors" in resp:
            raise HttpError(400, f"GraphQL errors: {resp['errors']}", url)
        return resp.get("data", {})
    except HttpError as e:
        log.error(f"GraphQL {query_key} failed: {e}")
        raise


# === High-level helpers ===

def root_categories(asset_type: str) -> list[dict]:
    """asset_type: 'music' | 'sfx' | 'footage' | ..."""
    data = _run("RootCategories", {"assetType": asset_type}, version=1)
    return data.get("rootCategories", [])


def song_list(page: int = 1, take: int = 50, sort_type: str = "STAFF_PICKS",
              vocal_type: str = "VOCAL_AND_INSTRUMENTS", category_ids: list[int] | None = None,
              excluded_category_ids: list[int] | None = None, search_term: str = "",
              is_with_stems_only: bool = False, excluded_song_ids: list[str] | None = None,
              bpm_min: int | None = None, bpm_max: int | None = None,
              duration_min: int | None = None, duration_max: int | None = None) -> dict:
    v = {
        "isAuthenticated": True,
        "searchTerm": search_term,
        "typeId": 1,
        "take": take,
        "page": page,
        "songSortType": sort_type,
        "vocalType": vocal_type,
        "categoryIds": category_ids or [],
        "excludedCategoryIds": excluded_category_ids or [],
        "isWithStemsOnly": is_with_stems_only,
        "excludedSongIds": excluded_song_ids or [],
    }
    if bpm_min is not None: v["bpmMin"] = bpm_min
    if bpm_max is not None: v["bpmMax"] = bpm_max
    if duration_min is not None: v["durationMin"] = duration_min
    if duration_max is not None: v["durationMax"] = duration_max
    return _run("SongList", v, version=2)


def sfx_list(page: int = 1, sort_by: str = "STAFF_PICKS", category_ids: str = "",
             tags: str = "", term: str = "") -> dict:
    v = {
        "categoryIds": category_ids,
        "page": page,
        "tags": tags,
        "term": term,
        "sortBy": sort_by,
    }
    return _run("SfxList", v, version=1)


def clip_list(page: int = 1, filter_categories: list[int] | None = None,
              search_terms: list[str] | None = None, sort_type: int = 1, query_type: int = 1,
              orientation: str | None = None, frame_rate: str | None = None,
              duration_min: int | None = None, duration_max: int | None = None,
              include_ai_content: bool = True) -> dict:
    v = {
        "page": page,
        "queryType": query_type,
        "filterCategories": filter_categories or [],
        "searchTerms": search_terms or [],
        "sortType": sort_type,
        "includeAIContent": include_ai_content,
    }
    if orientation: v["orientation"] = orientation
    if frame_rate: v["frameRate"] = frame_rate
    if duration_min is not None: v["durationMin"] = duration_min
    if duration_max is not None: v["durationMax"] = duration_max
    return _run("ClipList", v, version=1)


def catalog(page: int = 1, take: int = 100) -> dict:
    """Footage catalog (collection of footage 'stories')."""
    return _run("Catalog", {"page": page, "take": take}, version=1)


def template_root_categories() -> list[dict]:
    # templateRootCategories is on v1/graphql (verified)
    return _run("TemplateRootCategories", {}, version=1).get("templateRootCategories", [])


def template_search_filters() -> dict:
    # templateSearchFilters is on v1/graphql (verified)
    return _run("templateSearchFilters", {}, version=1).get("templateSearchFilters", {})


def templates_list(page: int = 1, take: int = 50, sort_by: str = "STAFF_PICKS",
                   software_names: list | None = None, software_versions: list | None = None,
                   resolutions: list | None = None, aspect_ratios: list | None = None,
                   plugins: list | None = None, categories: list | None = None,
                   search_terms: list | None = None) -> list[dict]:
    v = {
        "payload": {
            "page": page,
            "take": take,
            "softwareNames": software_names or [],
            "softwareVersions": software_versions or [],
            "resolutions": resolutions or [],
            "aspectRatios": aspect_ratios or [],
            "plugins": plugins or [],
            "categories": categories or [],
            "searchTerms": search_terms or [],
            "sortBy": sort_by,
        }
    }
    return _run("TemplatesList", v, version=2).get("templatesList", [])


def luts(lut_base_preview_id: str, page: int = 1, take: int = 20,
         saturation: list[str] | None = None, temperature: list[str] | None = None,
         contrast: list[str] | None = None, video_category_name: list[str] | None = None,
         mood_category_name: list[str] | None = None) -> list[dict]:
    v = {
        "lutBasePreviewId": lut_base_preview_id,
        "page": page,
        "take": take,
    }
    if saturation: v["saturation"] = saturation
    if temperature: v["temperature"] = temperature
    if contrast: v["contrast"] = contrast
    if video_category_name: v["videoCategoryName"] = video_category_name
    if mood_category_name: v["moodCategoryName"] = mood_category_name
    # Luts query is on v1/graphql (not v2)
    return _run("Luts", v, version=1).get("luts", [])


def luts_by_ids(ids: list[str]) -> list[dict]:
    # LutsByIds is also on v1 (verified from HAR)
    return _run("LutsByIds", {"ids": ids}, version=1).get("lutsByIds", [])


def search_terms_autosuggestions(asset_type: str) -> list[str]:
    """asset_type: 'MUSIC' | 'SFX' | 'FOOTAGE' | 'LUT' | 'TEMPLATE' (uppercase)."""
    data = _run("searchTermsAutosuggestions", {"assetType": asset_type}, version=1)
    return data.get("searchTermsAutosuggestions", {}).get("terms", [])
