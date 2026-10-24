from __future__ import annotations



import csv

from dataclasses import dataclass

from pathlib import Path



from napolnenie.query import build_web_query

from napolnenie.sources.base import SearchResult

from napolnenie.sources.web_ddg import DuckDuckGoImages

from napolnenie.storage import download_image, image_slug_for_row

from napolnenie.web_pick import pick_best_hit



WEB_REPORT_COLUMNS = [

    "source_file",

    "row_num",

    "group",

    "series_raw",

    "query_sent",

    "web_query",

    "source",

    "status",

    "confidence",

    "image_url",

    "local_path",

    "image_title",

    "error",

]





@dataclass

class WebRowResult:

    source_file: str

    row_num: int

    group: str

    series_raw: str

    query_sent: str

    web_query: str

    source: str = "ddg"

    status: str = "not_found"

    confidence: str = "0.5"

    image_url: str = ""

    local_path: str = ""

    image_title: str = ""

    error: str = ""





def load_parsed_rows(path: Path) -> list[dict]:

    with open(path, encoding="utf-8-sig", newline="") as f:

        return list(csv.DictReader(f))





def run_web_search(

    parsed_rows: list[dict],

    *,

    out_dir: Path,

    images_dir: Path,

    max_results: int = 8,

    min_interval: float = 1.5,

    download: bool = True,

    unique_query: bool = False,

    verbose: bool = False,

) -> list[WebRowResult]:

    """По одной попытке поиска и одному файлу на каждую строку parsed.csv (row_num)."""

    client = DuckDuckGoImages(

        cache_dir=out_dir / "_cache" / "ddg",

        max_results=max_results,

        min_interval=min_interval,

    )

    search_cache: dict[str, SearchResult] = {}

    results: list[WebRowResult] = []



    total = len(parsed_rows)

    for idx, row in enumerate(parsed_rows, start=1):

        query_sent = (row.get("query_sent") or "").strip()

        group = (row.get("group") or "").strip()

        web_q = build_web_query(query_sent, group)

        row_num = int(row.get("row_num") or 0)

        if verbose:

            print(f"[{idx}/{total}] row {row_num} | {query_sent} | {web_q}", flush=True)

        wr = WebRowResult(

            source_file=row.get("source_file", ""),

            row_num=row_num,

            group=group,

            series_raw=row.get("series_raw", ""),

            query_sent=query_sent,

            web_query=web_q,

        )



        if not query_sent:

            wr.status = "error"

            wr.error = "пустой query_sent"

            results.append(wr)

            continue



        cache_key = web_q if unique_query else f"{web_q}#r{row_num}"

        if cache_key not in search_cache:

            search_cache[cache_key] = client.search(web_q)

        sr = search_cache[cache_key]



        if sr.error:

            wr.status = "error"

            wr.error = sr.error

        else:

            chosen = pick_best_hit(query_sent, sr.hits, set())

            if chosen:

                wr.status = "needs_review"

                wr.image_url = chosen.image_url

                wr.image_title = chosen.description

                if download:

                    dest = images_dir / image_slug_for_row(row_num, query_sent)

                    ok, msg, _ = download_image(chosen.image_url, dest)

                    if ok:

                        wr.local_path = str(_find_image(dest))

                    else:

                        wr.error = msg

            else:

                wr.status = "not_found"

                if sr.hits:

                    wr.error = "в выдаче нет картинки с MPN в заголовке/ссылке (отброшен generic BGA)"

                else:

                    wr.error = "пустая выдача DDG"



        results.append(wr)



    return results





def _find_image(base: Path) -> Path:

    if base.is_file():

        return base

    for p in base.parent.glob(base.name + ".*"):

        if p.is_file():

            return p

    return base





def write_web_report(results: list[WebRowResult], path: Path) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8-sig", newline="") as f:

        w = csv.DictWriter(f, fieldnames=WEB_REPORT_COLUMNS)

        w.writeheader()

        for r in results:

            w.writerow(

                {

                    "source_file": r.source_file,

                    "row_num": r.row_num,

                    "group": r.group,

                    "series_raw": r.series_raw,

                    "query_sent": r.query_sent,

                    "web_query": r.web_query,

                    "source": r.source,

                    "status": r.status,

                    "confidence": r.confidence,

                    "image_url": r.image_url,

                    "local_path": r.local_path,

                    "image_title": r.image_title,

                    "error": r.error,

                }

            )


