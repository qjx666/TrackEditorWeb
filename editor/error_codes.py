from enum import Enum


class EditorError(Enum):
    NO_TRACK = 520
    EDITOR = 520
    RENAME_SEGMENT = 521
    REMOVE_SEGMENT = 522
    GET_SEGMENT = 523
    GET_TRACK = 524
    GET_SUMMARY = 525
    SAVE_SESSION = 526
    REMOVE_SESSION = 527
    RENAME_SESSION = 528
    DOWNLOAD_SESSION = 529
    GET_SEGMENTS_LINKS = 530
    REVERSE_SEGMENT = 531
    CHANGE_SEGMENTS_ORDER = 532
    DIVIDE_SEGMENT = 533
