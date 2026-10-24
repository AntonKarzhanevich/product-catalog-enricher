from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import yaml

from napolnenie.env import project_root, require_env
from napolnenie.network_check import run_connectivity_checks
from napolnenie.parser import parse_xlsx
from napolnenie.query import apply_queries_all
from napolnenie.mouser_runner import load_parsed_rows as load_mouser_rows
from napolnenie.mouser_runner import (
    download_mouser_images_from_report,
    merge_download_paths_into_report,
    run_mouser_search,
    write_mouser_report,
)
from napolnenie.sources.mouser import MouserClient
from napolnenie.storage import (
    clean_mouser_artifacts,
    clean_web2_artifacts,
    clean_web_artifacts,
    clean_web_cascade_artifacts,
)
from napolnenie.web_cascade_runner import (
    load_web2_report,
    merge_cascade_report,
    parsed_rows_for_v1_tail,
    write_cascade_report,
)
from napolnenie.web2_runner import (
    load_profile,
    run_web2_search,
    write_stats,
    write_web2_report,
)
from napolnenie.web_runner import load_parsed_rows, run_web_search, write_web_report

PARSED_COLUMNS = [
    "source_file",
    "row_num",
    "group",
    "series_raw",
    "series_head",
    "series_clean",
    "art_log",
    "verified",
    "query_sent",
    "query_fallback",
    "normalize_rule",
    "desc_log",
]


def _default_out_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "out"


def cmd_parse(args: argparse.Namespace) -> int:
    xlsx_path = Path(args.xlsx)
    if not xlsx_path.is_file():
        print(f"Файл не найден: {xlsx_path}", file=sys.stderr)
        return 1

    result = parse_xlsx(xlsx_path)
    rows = apply_queries_all(result.rows)

    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (args.output or "parsed.csv")

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PARSED_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "source_file": r.source_file,
                    "row_num": r.row_num,
                    "group": r.group,
                    "series_raw": r.series_raw,
                    "series_head": r.series_head,
                    "series_clean": r.series_clean,
                    "art_log": r.art_e,
                    "verified": "true" if r.verified else "false",
                    "query_sent": r.query_sent,
                    "query_fallback": r.query_fallback,
                    "normalize_rule": r.normalize_rule,
                    "desc_log": r.desc,
                }
            )

    print(f"Группа: {result.group}")
    print(f"Строк: {len(rows)}")
    print(f"Записано: {out_path}")
    return 0


def _load_web_config() -> dict:
    cfg = project_root() / "config" / "sources.yaml"
    if cfg.is_file():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        return data.get("web") or {}
    return {}


def _load_mouser_config() -> dict:
    cfg = project_root() / "config" / "sources.yaml"
    if cfg.is_file():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        return data.get("mouser") or {}
    return {}


def _load_probe_queries() -> list[str]:
    cfg = project_root() / "config" / "sources.yaml"
    if cfg.is_file():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        queries = data.get("m2_probe_queries")
        if queries:
            return list(queries)
    return ["ALC3248", "NB669AEVD", "216-0772034", "SY8033BDBC", "LTC2978UP"]


def cmd_mouser_probe(args: argparse.Namespace) -> int:
    try:
        api_key = require_env("MOUSER_API_KEY")
    except RuntimeError as e:
        print(e, file=sys.stderr)
        print(
            "Регистрация: https://www.mouser.com/api-hub/ → Search API Key",
            file=sys.stderr,
        )
        return 1

    queries = list(args.query) if args.query else _load_probe_queries()
    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()
    cache_dir = out_dir / "_cache" / "mouser"
    client = MouserClient(api_key=api_key, cache_dir=cache_dir)

    rows_out: list[dict] = []
    found = 0
    for q in queries:
        result = client.search_part(q)
        hit = result.hits[0] if result.hits else None
        if hit:
            found += 1
        rows_out.append(
            {
                "query": q,
                "status": "found" if hit else ("error" if result.error else "not_found"),
                "search_mode": result.search_mode,
                "image_url": hit.image_url if hit else "",
                "product_url": hit.product_url if hit else "",
                "mouser_part_number": hit.mouser_part_number if hit else "",
                "manufacturer_part_number": hit.manufacturer_part_number if hit else "",
                "manufacturer": hit.manufacturer if hit else "",
                "raw_cache": result.raw_cache_path,
                "error": result.error,
            }
        )
        status = rows_out[-1]["status"]
        err = rows_out[-1].get("error") or ""
        line = f"  {q}: {status}"
        if hit:
            line += f" → {hit.image_url[:60]}..."
        elif err:
            line += f" — {err[:120]}"
        print(line)

    out_path = out_dir / (args.output or "mouser_probe.csv")
    fieldnames = list(rows_out[0].keys()) if rows_out else ["query"]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"\nНайдено: {found}/{len(queries)}")
    print(f"Кэш: {cache_dir}")
    print(f"Отчёт: {out_path}")
    return 0 if found > 0 else 2


def cmd_mouser_download(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()
    report_path = Path(args.report) if args.report else out_dir / "mouser_report.csv"
    if not report_path.is_file():
        print(f"Нет отчёта: {report_path}. Сначала: python -m napolnenie mouser-run", file=sys.stderr)
        return 1

    checks = run_connectivity_checks()
    mouser_ok = any(c.name.startswith("Mouser") and c.ok for c in checks)
    if not mouser_ok:
        print("Mouser с этой сети недоступен (403). Включите VPN EU/US и повторите.", file=sys.stderr)
        return 2

    images_dir = out_dir / "images" / "mouser"
    images_dir.mkdir(parents=True, exist_ok=True)
    print(f"Отчёт: {report_path}")
    print(f"Папка: {images_dir}\n")

    ok_count, total, downloaded = download_mouser_images_from_report(
        report_path, images_dir, verbose=True
    )
    merge_download_paths_into_report(report_path, downloaded)

    print(f"\nСкачано: {ok_count}/{total}")
    print(f"Обновлён отчёт: {report_path}")
    return 0 if ok_count > 0 else 2


def cmd_mouser_run(args: argparse.Namespace) -> int:
    try:
        api_key = require_env("MOUSER_API_KEY")
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    parsed = _parsed_path(args)
    if not parsed.is_file():
        print(f"Нет файла {parsed}. Сначала: python -m napolnenie parse ...", file=sys.stderr)
        return 1

    rows = load_mouser_rows(parsed)
    if getattr(args, "limit", None):
        rows = rows[: args.limit]

    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()
    if getattr(args, "clean", False):
        removed = clean_mouser_artifacts(out_dir)
        if removed:
            print("Очищено:")
            for item in removed:
                print(f"  {item}")
            print()

    mouser_cfg = _load_mouser_config()
    cache_dir = out_dir / "_cache" / "mouser"
    client = MouserClient(
        api_key=api_key,
        cache_dir=cache_dir,
        min_interval=float(mouser_cfg.get("min_interval_sec", 2.0)),
    )
    images_dir = out_dir / "images" / "mouser"

    print(f"Строк к обработке: {len(rows)}")
    print("Поиск в Mouser API…\n")

    results = run_mouser_search(
        rows,
        client=client,
        images_dir=images_dir,
        download=not getattr(args, "no_download", False),
    )

    found = sum(1 for r in results if r.status == "found")
    with_file = sum(1 for r in results if r.status == "found" and r.local_path)
    errors = sum(1 for r in results if r.status == "error")

    out_path = out_dir / (getattr(args, "output", None) or "mouser_report.csv")
    write_mouser_report(results, out_path)

    nf = [r for r in results if r.status in ("not_found", "error")]
    if nf:
        nf_path = out_dir / "mouser_not_found.csv"
        write_mouser_report(nf, nf_path)

    print(f"\nНайдено: {found}/{len(results)} (файлов: {with_file}, error: {errors})")
    print(f"Кэш: {cache_dir}")
    print(f"Отчёт: {out_path}")
    if nf:
        print(f"Не найдено/error: {out_dir / 'mouser_not_found.csv'} ({len(nf)} строк)")
    return 0 if found > 0 else 2


def _parsed_path(args: argparse.Namespace) -> Path:
    if getattr(args, "parsed", None):
        return Path(args.parsed)
    return _default_out_dir() / "parsed.csv"


def _run_web_cmd(args: argparse.Namespace, *, probe: bool) -> int:
    parsed = _parsed_path(args)
    if not parsed.is_file():
        print(f"Нет файла {parsed}. Сначала: python -m napolnenie parse ...", file=sys.stderr)
        return 1

    rows = load_parsed_rows(parsed)
    web_cfg = _load_web_config()
    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()

    if getattr(args, "clean", False):
        removed = clean_web_artifacts(out_dir)
        if removed:
            print("Очищено:")
            for p in removed:
                print(f"  {p}")
        else:
            print("Очищать нечего — артефактов web не было.")
        print()

    if probe:
        probe_limit = int(web_cfg.get("probe_limit", 30))
        limit = int(args.limit) if args.limit is not None else probe_limit
        rows = rows[:limit]
        if not rows:
            print("parsed.csv пуст.", file=sys.stderr)
            return 1
    elif getattr(args, "limit", None):
        rows = rows[: int(args.limit)]

    images_dir = out_dir / "images" / "web"
    download = not getattr(args, "no_download", False)

    print(f"Строк к обработке: {len(rows)}")
    print("Поиск в DuckDuckGo (пакет ddgs)…\n")
    results = run_web_search(
        rows,
        out_dir=out_dir,
        images_dir=images_dir,
        max_results=int(web_cfg.get("max_results", 8)),
        min_interval=float(web_cfg.get("min_interval_sec", 1.5)),
        download=download,
        verbose=True,
    )

    found = sum(1 for r in results if r.status == "needs_review")
    for r in results:
        line = f"  {r.query_sent}: {r.status}"
        if r.image_url:
            line += f" → {r.image_url[:55]}..."
        if r.error:
            line += f" ({r.error[:60]})"
        print(line)

    out_name = "web_probe.csv" if probe else "web_report.csv"
    out_path = out_dir / (getattr(args, "output", None) or out_name)
    write_web_report(results, out_path)
    not_found_path = out_dir / "web_not_found.csv"
    nf = [r for r in results if r.status == "not_found"]
    if nf:
        write_web_report(nf, not_found_path)

    print(f"\nНайдено (needs_review): {found}/{len(results)}")
    print(f"Отчёт: {out_path}")
    if nf:
        print(f"Не найдено: {not_found_path} ({len(nf)} строк)")
    return 0 if found > 0 else 2


def cmd_web_probe(args: argparse.Namespace) -> int:
    return _run_web_cmd(args, probe=True)


def cmd_web_run(args: argparse.Namespace) -> int:
    return _run_web_cmd(args, probe=False)


def _run_web2_cmd(args: argparse.Namespace, *, probe: bool) -> int:
    parsed = _parsed_path(args)
    if not parsed.is_file():
        print(f"Нет файла {parsed}. Сначала: python -m napolnenie parse ...", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()
    if getattr(args, "clean", False):
        removed = clean_web2_artifacts(out_dir)
        if removed:
            print("Очищено:")
            for p in removed:
                print(f"  {p}")
        else:
            print("Очищать нечего — артефактов web2 не было.")
        print()

    profile_name = getattr(args, "profile", None) or "bga_laptop_ic"
    try:
        profile = load_profile(profile_name)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    rows = load_parsed_rows(parsed)
    if probe:
        probe_limit = int((profile.get("ddgs_text", {}) or {}).get("probe_limit", 30))
        limit = int(args.limit) if args.limit is not None else probe_limit
        rows = rows[:limit]
    elif getattr(args, "limit", None):
        rows = rows[: int(args.limit)]
    if not rows:
        print("parsed.csv пуст.", file=sys.stderr)
        return 1

    images_dir = out_dir / "images" / "web2"
    download = not getattr(args, "no_download", False)
    print(f"Строк к обработке: {len(rows)}")
    print(f"Профиль: {profile_name}; источники: {profile.get('sources', [])}\n")

    results, metrics = run_web2_search(
        rows,
        out_dir=out_dir,
        images_dir=images_dir,
        profile=profile,
        download=download,
        verbose=True,
    )

    found = sum(1 for r in results if r.status == "needs_review")
    for r in results:
        line = f"  {r.query_sent}: {r.status}"
        if r.source:
            line += f" [{r.source}]"
        if r.image_url:
            line += f" → {r.image_url[:55]}..."
        if r.error:
            line += f" ({r.error[:60]})"
        print(line)

    out_name = "web2_probe.csv" if probe else "web2_report.csv"
    out_path = out_dir / (getattr(args, "output", None) or out_name)
    write_web2_report(results, out_path)
    nf = [r for r in results if r.status == "not_found"]
    if nf:
        write_web2_report(nf, out_dir / "web2_not_found.csv")
    write_stats(metrics, out_dir / "web2_stats.csv")

    print(f"\nНайдено (needs_review): {found}/{len(results)}")
    print(f"Отчёт: {out_path}")
    if nf:
        print(f"Не найдено: {out_dir / 'web2_not_found.csv'} ({len(nf)} строк)")
    print(f"Метрики per-source: {out_dir / 'web2_stats.csv'}")
    return 0 if found > 0 else 2


def cmd_web2_probe(args: argparse.Namespace) -> int:
    return _run_web2_cmd(args, probe=True)


def cmd_web2_run(args: argparse.Namespace) -> int:
    return _run_web2_cmd(args, probe=False)


def cmd_web_cascade(args: argparse.Namespace) -> int:
    parsed = _parsed_path(args)
    if not parsed.is_file():
        print(f"Нет файла {parsed}. Сначала: python -m napolnenie parse ...", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir()
    if getattr(args, "clean", False):
        removed = clean_web_cascade_artifacts(out_dir)
        if removed:
            print("Очищено:")
            for p in removed:
                print(f"  {p}")
            print()

    profile_name = getattr(args, "profile", None) or "bga_laptop_ic"
    try:
        profile = load_profile(profile_name)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    rows = load_parsed_rows(parsed)
    if getattr(args, "limit", None):
        rows = rows[: int(args.limit)]
    if not rows:
        print("parsed.csv пуст.", file=sys.stderr)
        return 1

    web2_report_path = out_dir / "web2_report.csv"
    skip_web2 = getattr(args, "skip_web2", False)
    download = not getattr(args, "no_download", False)

    if skip_web2:
        if not web2_report_path.is_file():
            print(
                f"Нет {web2_report_path}. Уберите --skip-web2 или сначала: web2-run",
                file=sys.stderr,
            )
            return 1
        print(f"web2: из отчёта {web2_report_path}")
        web2_results = load_web2_report(web2_report_path)
        if len(web2_results) != len(rows):
            print(
                f"Предупреждение: web2_report {len(web2_results)} строк, parsed {len(rows)}",
                file=sys.stderr,
            )
    else:
        if getattr(args, "clean", False) is False and web2_report_path.is_file():
            print("web2: полный прогон (есть старый web2_report; для хвоста v1: --skip-web2)")
        images_dir2 = out_dir / "images" / "web2"
        print(f"web2: {len(rows)} строк; профиль {profile_name}\n")
        web2_results, metrics = run_web2_search(
            rows,
            out_dir=out_dir,
            images_dir=images_dir2,
            profile=profile,
            download=download,
            verbose=True,
        )
        write_web2_report(web2_results, web2_report_path)
        nf2 = [r for r in web2_results if r.status == "not_found"]
        if nf2:
            write_web2_report(nf2, out_dir / "web2_not_found.csv")
        write_stats(metrics, out_dir / "web2_stats.csv")
        w2_ok = sum(1 for r in web2_results if r.status == "needs_review" and r.local_path)
        print(f"\nweb2 готово: {w2_ok}/{len(web2_results)} с файлом\n")

    tail_rows = parsed_rows_for_v1_tail(rows, web2_results)
    web1_results: list = []
    if tail_rows:
        web_cfg = _load_web_config()
        images_dir1 = out_dir / "images" / "web"
        print(f"web1 (DDG): хвост {len(tail_rows)} строк\n")
        web1_results = run_web_search(
            tail_rows,
            out_dir=out_dir,
            images_dir=images_dir1,
            max_results=int(web_cfg.get("max_results", 8)),
            min_interval=float(web_cfg.get("min_interval_sec", 1.5)),
            download=download,
            verbose=True,
        )
        write_web_report(web1_results, out_dir / "web_v1_fallback.csv")
        w1_ok = sum(1 for r in web1_results if r.status == "needs_review" and r.local_path)
        print(f"\nweb1 хвост: {w1_ok}/{len(tail_rows)} с файлом\n")
    else:
        print("web1: пропуск — все строки закрыты web2\n")

    cascade = merge_cascade_report(web2_results, web1_results)
    cascade_path = out_dir / (getattr(args, "output", None) or "web_cascade_report.csv")
    write_cascade_report(cascade, cascade_path)

    nf = [r for r in cascade if r.cascade_status == "not_found"]
    if nf:
        write_cascade_report(nf, out_dir / "web_cascade_not_found.csv")

    found2 = sum(1 for r in cascade if r.cascade_status == "found_web2")
    found1 = sum(1 for r in cascade if r.cascade_status == "found_web1")
    with_file = sum(1 for r in cascade if (r.local_path or "").strip())

    print(f"Каскад: web2={found2}, web1 fallback={found1}, not_found={len(nf)}")
    print(f"С файлом: {with_file}/{len(cascade)}")
    print(f"Отчёт: {cascade_path}")
    if nf:
        print(f"Не найдено: {out_dir / 'web_cascade_not_found.csv'} ({len(nf)} строк)")
    return 0 if with_file > 0 else 2


def cmd_doctor(_args: argparse.Namespace) -> int:
    print("Проверка доступности источников (без API-ключей):\n")
    blocked_api = False
    for chk in run_connectivity_checks():
        mark = "OK" if chk.ok else "FAIL"
        print(f"  [{mark}] {chk.name}: {chk.status}")
        if not chk.ok and chk.hint:
            print(f"         → {chk.hint}")
        if not chk.ok and "Mouser" in chk.name:
            blocked_api = True

    load_dotenv = __import__("napolnenie.env", fromlist=["load_dotenv"]).load_dotenv
    load_dotenv()
    key = os.environ.get("MOUSER_API_KEY", "").strip()
    if key:
        print(f"\nMOUSER_API_KEY: задан ({len(key)} символов)")
    else:
        print("\nMOUSER_API_KEY: не задан")

    if blocked_api:
        print("\nВывод: Mouser API с этой сети не достучаться — это не баг парсера query.")
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="napolnenie", description="Поиск картинок для 1С xlsx")
    sub = p.add_subparsers(dest="command", required=True)

    parse_p = sub.add_parser("parse", help="Разобрать xlsx и построить query (без сети)")
    parse_p.add_argument("xlsx", type=Path, help="Путь к xlsx из data/raw")
    parse_p.add_argument("-o", "--output", help="Имя CSV (по умолчанию parsed.csv)")
    parse_p.add_argument("--out-dir", type=Path, help="Папка вывода (по умолчанию data/out)")
    parse_p.set_defaults(func=cmd_parse)

    mouser_p = sub.add_parser("mouser-probe", help="Поиск картинок в Mouser (5 тестовых MPN)")
    mouser_p.add_argument(
        "query",
        nargs="*",
        help="MPN для проверки (по умолчанию — из config/sources.yaml)",
    )
    mouser_p.add_argument("-o", "--output", help="Имя CSV (по умолчанию mouser_probe.csv)")
    mouser_p.add_argument("--out-dir", type=Path, help="Папка вывода")
    mouser_p.set_defaults(func=cmd_mouser_probe)

    mouser_run_p = sub.add_parser("mouser-run", help="Поиск картинок в Mouser по всему parsed.csv")
    mouser_run_p.add_argument(
        "--parsed",
        type=Path,
        help="Путь к parsed.csv (по умолчанию data/out/parsed.csv)",
    )
    mouser_run_p.add_argument("-o", "--output", help="Имя CSV (по умолчанию mouser_report.csv)")
    mouser_run_p.add_argument("--out-dir", type=Path, help="Папка вывода")
    mouser_run_p.add_argument("--limit", type=int, help="Макс. строк")
    mouser_run_p.add_argument(
        "--clean",
        action="store_true",
        help="Перед прогоном удалить mouser_report, images/mouser, _cache/mouser",
    )
    mouser_run_p.add_argument("--no-download", action="store_true", help="Только URL, без скачивания")
    mouser_run_p.set_defaults(func=cmd_mouser_run)

    mouser_dl_p = sub.add_parser(
        "mouser-download",
        help="Скачать картинки по строкам found в mouser_report.csv (VPN)",
    )
    mouser_dl_p.add_argument(
        "--report",
        type=Path,
        help="Путь к mouser_report.csv (по умолчанию data/out/mouser_report.csv)",
    )
    mouser_dl_p.add_argument("--out-dir", type=Path, help="Папка вывода")
    mouser_dl_p.set_defaults(func=cmd_mouser_download)

    doctor_p = sub.add_parser("doctor", help="Проверка сети (Mouser/Digi-Key/DDG)")
    doctor_p.set_defaults(func=cmd_doctor)

    for name, func, help_text in (
        ("web-probe", cmd_web_probe, "Веб-поиск v1 (DDG Images): первые N строк parsed.csv"),
        ("web-run", cmd_web_run, "Веб-поиск v1 (DDG Images) по всему parsed.csv"),
        (
            "web2-probe",
            cmd_web2_probe,
            "Веб-поиск v2 (trusted listings): первые N строк parsed.csv",
        ),
        (
            "web2-run",
            cmd_web2_run,
            "Веб-поиск v2 (trusted listings) по всему parsed.csv",
        ),
    ):
        wp = sub.add_parser(name, help=help_text)
        wp.add_argument(
            "--parsed",
            type=Path,
            help="Путь к parsed.csv (по умолчанию data/out/parsed.csv)",
        )
        wp.add_argument("-o", "--output", help="Имя CSV отчёта")
        wp.add_argument("--out-dir", type=Path, help="Папка вывода")
        wp.add_argument(
            "--limit",
            type=int,
            help="Макс. строк (probe: по умолчанию probe_limit из sources.yaml)",
        )
        wp.add_argument(
            "--clean",
            action="store_true",
            help="Перед прогоном удалить web_probe/report, images/web, _cache/ddg",
        )
        wp.add_argument("--no-download", action="store_true", help="Только URL, без скачивания")
        if name.startswith("web2"):
            wp.add_argument(
                "--profile",
                default="bga_laptop_ic",
                help="Имя профиля группы (config/sources/<name>.yaml)",
            )
        wp.set_defaults(func=func)

    cascade_p = sub.add_parser(
        "web-cascade",
        help="web2 по всем строкам, затем web1 (DDG) только на miss web2",
    )
    cascade_p.add_argument("--parsed", type=Path, help="parsed.csv")
    cascade_p.add_argument("-o", "--output", help="Имя сводного отчёта (web_cascade_report.csv)")
    cascade_p.add_argument("--out-dir", type=Path, help="Папка вывода")
    cascade_p.add_argument("--limit", type=int, help="Макс. строк")
    cascade_p.add_argument(
        "--clean",
        action="store_true",
        help="Очистить web, web2 и отчёты каскада перед прогоном",
    )
    cascade_p.add_argument(
        "--skip-web2",
        action="store_true",
        help="Не гонять web2 — взять готовый web2_report.csv, только хвост web1",
    )
    cascade_p.add_argument("--no-download", action="store_true", help="Без скачивания файлов")
    cascade_p.add_argument(
        "--profile",
        default="bga_laptop_ic",
        help="Профиль web2 (config/sources/<name>.yaml)",
    )
    cascade_p.set_defaults(func=cmd_web_cascade)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
