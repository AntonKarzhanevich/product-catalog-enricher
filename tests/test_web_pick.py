from napolnenie.sources.base import ImageHit
from napolnenie.web_pick import hit_matches_mpn, is_generic_stock, pick_best_hit


def test_generic_bga_skipped_without_mpn():
    hits = [
        ImageHit(
            query="x",
            image_url="https://static.tildacdn.com/New_bga_chip.jpg",
            description="Курс по пайке BGA чипов",
        ),
        ImageHit(
            query="x",
            image_url="https://shop.example/LTC2978UP-photo.jpg",
            description="LTC2978UP power manager",
        ),
    ]
    picked = pick_best_hit("LTC2978UP", hits, set())
    assert picked is not None
    assert "LTC2978UP" in picked.image_url


def test_same_url_not_reused():
    url = "https://static.tildacdn.com/New_bga_chip.jpg"
    hits = [
        ImageHit(query="x", image_url=url, description="NB669AEVD chip"),
    ]
    used = {url}
    assert pick_best_hit("NB669AEVD", hits, used) is None


def test_mpn_in_title():
    hit = ImageHit(query="x", image_url="https://x.com/a.jpg", description="216-0772034 AMD")
    assert hit_matches_mpn("216-0772034", hit)
    assert is_generic_stock(
        ImageHit(query="x", image_url="https://t/New_bga_chip.jpg", description="курс")
    )
