# -*- coding: utf-8 -*-
"""auction/crawler.py(두인 수집기)를 모듈로 불러와 그 함수들을 그대로 쓴다.
이름이 같은 crawler.py 가 여러 폴더에 있어서 경로로 직접 불러온다."""
import importlib.util
import os
import sys

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auction", "crawler.py")
_spec = importlib.util.spec_from_file_location("auction_crawler", _PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["auction_crawler"] = _mod
_spec.loader.exec_module(_mod)


def __getattr__(name):
    return getattr(_mod, name)
