import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.crawler_core import Crawler, Settings, Site, parse_list, parse_list_date
from common.search_adapters import jjan_rest, knnews_json
from common.verified_selectors import VERIFIED_SELECTORS as V


def site(name):
    base = dict(name="레지스트리에 없는 신문", search_url="u", list_item_sel="x", list_title_sel="a", list_date_sel="", article_date_sel="x", article_body_sel="b")
    base.update({k: v for k, v in V[name].items() if k in ("list_item_sel", "list_title_sel", "list_date_sel", "search_adapter")})
    return Site(**base)


class Fake:
    """JSON 응답을 돌려주는 가짜 fetcher. 마지막 요청을 기록한다."""

    def __init__(self, payload, raw_encoding="utf-8"):
        self.payload, self.enc, self.calls = payload, raw_encoding, []

    def _bytes(self):
        return json.dumps(self.payload, ensure_ascii=False).encode(self.enc)

    def post_raw(self, url, data=None, headers=None, timeout=15):
        self.calls.append(("POST", url, data, headers))
        return self._bytes()

    def get_raw(self, url, headers=None, timeout=15):
        self.calls.append(("GET", url, None, headers))
        return self._bytes()


KN = {"total": 17977, "CONTENTS_LIST": [
    {"ARTICLE_ID": "1553947", "ART_TITLE": "폐쇄했다더니… 꺼지지 않는 창원 서성동 ‘홍등’", "PRESSDATE": "2026-10-29 19:27:58"},
    {"DOCID": "1553941", "ART_TITLE": "A & B <사업> 보상", "PRESSDATE": "2026-10-26 18:56:31"}]}


def test_knnews_adapter_builds_the_request_and_the_list():
    f = Fake(KN)
    url, html = knnews_json(site("경남신문"), "보상", 3, f)
    method, u, data, headers = f.calls[0]
    assert method == "POST" and u == "https://search.knnews.co.kr/openSearch/totalSearch"
    assert data["startCount"] == "20" and data["page"] == "3" and data["sort"] == "DATE/DESC" and data["query"] == "보상"   # 3쪽 = 시작위치 20, 최신순
    items = parse_list(html, url, site("경남신문"))
    assert [i["title"] for i in items] == ["폐쇄했다더니… 꺼지지 않는 창원 서성동 ‘홍등’", "A & B <사업> 보상"]          # HTML 특수문자도 그대로
    assert items[0]["link"] == "https://www.knnews.co.kr/news/articleView.php?idxno=1553947"
    assert items[1]["link"].endswith("idxno=1553941")                      # ARTICLE_ID 가 없으면 DOCID
    assert parse_list_date(items[0]["list_date"]) == "2026-10-29"


def test_knnews_response_with_wrong_charset_header_is_decoded_as_utf8():
    # 사이트는 JSON 을 UTF-8 로 보내면서 헤더에는 ISO-8859-1 이라 적는다. 바이트를 직접 해독해야 한다.
    items = parse_list(knnews_json(site("경남신문"), "보상", 1, Fake(KN, "utf-8"))[1], "https://x/", site("경남신문"))
    assert "서성동" in items[0]["title"]


JJ = {"searchText": "보상", "pages": {"totalElements": 2350}, "list": [
    {"id": "20261029500505", "title": "[금요칼럼] AI 시대 바다의 인재 양성", "viewTitle": "AI 시대 바다의 인재 양성",
     "createDate": "2026-10-29T07:17:27.221+0000", "updateDate": "2026-10-29T08:08:03.573+0000"},
    {"id": "20261016500049", "title": "미군 탄약고", "createDate": "2026-10-16T01:00:00.000+0000"}]}


def test_jjan_adapter_builds_url_and_list():
    f = Fake(JJ)
    url, html = jjan_rest(site("전북일보"), "보상", 2, f)
    assert f.calls[0][1] == "https://www.jjan.kr/rest/search?searchText=%EB%B3%B4%EC%83%81&searchType=all&from=&to=&page=2"
    items = parse_list(html, url, site("전북일보"))
    assert items[0]["link"] == "https://www.jjan.kr/article/20261029500505" and items[0]["title"] == "AI 시대 바다의 인재 양성"   # viewTitle 우선
    assert items[1]["title"] == "미군 탄약고"
    assert parse_list_date(items[0]["list_date"]) == "2026-10-29"           # updateDate
    assert parse_list_date(items[1]["list_date"]) == "2026-10-16"           # updateDate 가 없으면 createDate


def test_empty_result_gives_an_empty_list():
    assert parse_list(jjan_rest(site("전북일보"), "엉터리", 1, Fake({"list": []}))[1], "https://x/", site("전북일보")) == []


def test_fetch_search_page_dispatches_to_the_adapter():
    c = Crawler(Settings(save_directory=os.devnull, keywords=["보상"]))
    f = Fake(JJ)
    url, html = c.fetch_search_page(site("전북일보"), "보상", 1, f)
    assert "rest/search" in url and "article/20261029500505" in html


def test_registry_entries_for_the_three_new_sites():
    assert V["경남신문"]["search_adapter"] == "knnews_json" and V["전북일보"]["search_adapter"] == "jjan_rest"
    assert V["계룡일보"]["homepage_url"] == "https://www.krdaily.co.kr" and "krdaily.co.kr" in V["계룡일보"]["search_url"]
    assert V["전북일보"]["article_date_sel"] == "div.byline_info_wrap" and V["경남신문"]["article_date_sel"] == "li.loca_left"


def test_highlight_tags_in_api_titles_are_removed():
    payload = {"total": 1, "CONTENTS_LIST": [{"ARTICLE_ID": "1", "ART_TITLE": "김해 용두지구 <b>보상</b> 협의 &amp; 착수", "PRESSDATE": "2026-09-16 10:00:00"}]}
    items = parse_list(knnews_json(site("경남신문"), "보상", 1, Fake(payload))[1], "https://x/", site("경남신문"))
    assert items[0]["title"] == "김해 용두지구 보상 협의 & 착수"
    # 제목에 원래 있는 꺾쇠 낱말은 지우지 않는다
    p2 = {"CONTENTS_LIST": [{"ARTICLE_ID": "2", "ART_TITLE": "<사업> 시행 <B class=x>보상</B>", "PRESSDATE": "2026-09-16"}]}
    assert parse_list(knnews_json(site("경남신문"), "보상", 1, Fake(p2))[1], "https://x/", site("경남신문"))[0]["title"] == "<사업> 시행 보상"
