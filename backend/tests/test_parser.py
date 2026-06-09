"""
Parser tests with realistic Telegram message fixtures.
Run: pytest backend/tests/test_parser.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.parser import parse_listing, parse_auction_result_line, parse_results_message
from services.normalizer import normalize_model


# ── Listing parsing ──────────────────────────────────────────────────────────

class TestParseListing:
    def test_basic_listing_with_k_mileage(self):
        text = "2018 model BMW M3. 65k km. start price 18000€"
        r = parse_listing(text)
        assert r is not None
        assert r.year == 2018
        assert r.model_raw == "BMW M3"
        assert r.mileage_km == 65000
        assert r.start_price_eur == 18000

    def test_listing_with_decimal_mileage(self):
        text = "2015 model Nissan GT-R. 42.5k km. start price 25000€"
        r = parse_listing(text)
        assert r is not None
        assert r.mileage_km == 42500

    def test_listing_without_euro_sign(self):
        text = "2012 model Porsche 911. 80k km. start price 32000"
        r = parse_listing(text)
        assert r is not None
        assert r.start_price_eur == 32000

    def test_listing_multiline_message(self):
        text = "🚗 Auction lot #42\n2019 model Toyota Supra. 12k km. start price 45000€\nMore details here"
        r = parse_listing(text)
        assert r is not None
        assert r.year == 2019
        assert r.model_raw == "Toyota Supra"
        assert r.mileage_km == 12000

    def test_listing_returns_none_for_results_message(self):
        text = "A123, BMW M3 18000€ sold\nB456, Toyota Supra 25000€ not sold"
        r = parse_listing(text)
        assert r is None

    def test_listing_returns_none_for_empty(self):
        assert parse_listing("") is None
        assert parse_listing("Random text with no pattern") is None

    def test_listing_case_insensitive(self):
        text = "2017 MODEL Mercedes AMG. 55k KM. START PRICE 22000€"
        r = parse_listing(text)
        assert r is not None
        assert r.year == 2017


# ── Auction result line parsing ───────────────────────────────────────────────

class TestParseAuctionResultLine:
    def test_sold(self):
        r = parse_auction_result_line("A123, BMW M3 18000€ sold")
        assert r is not None
        assert r.lot_number == "A123"
        assert r.model_raw == "BMW M3"
        assert r.price_eur == 18000
        assert r.status == "sold"

    def test_not_sold(self):
        r = parse_auction_result_line("B456, Toyota Supra 25000€ not sold")
        assert r is not None
        assert r.lot_number == "B456"
        assert r.status == "not_sold"
        assert r.price_eur == 25000

    def test_canceled(self):
        r = parse_auction_result_line("C789, Porsche 911 canceled by seller")
        assert r is not None
        assert r.lot_number == "C789"
        assert r.status == "canceled"
        assert r.price_eur is None

    def test_returns_none_for_garbage(self):
        assert parse_auction_result_line("") is None
        assert parse_auction_result_line("Just some text") is None
        assert parse_auction_result_line("2018 model BMW. 65k km. start price 18000€") is None

    def test_model_with_spaces(self):
        r = parse_auction_result_line("D001, Mercedes C63 AMG 31000€ sold")
        assert r is not None
        assert r.model_raw == "Mercedes C63 AMG"
        assert r.price_eur == 31000


# ── Multi-line results message ────────────────────────────────────────────────

class TestParseResultsMessage:
    def test_mixed_results_block(self):
        msg = """Auction results 2024-01-15:
A101, BMW M3 18000€ sold
A102, Nissan GT-R 42000€ sold
A103, Toyota Supra 31000€ not sold
A104, Honda NSX canceled by seller
"""
        results = parse_results_message(msg)
        assert len(results) == 4
        statuses = [r.status for r in results]
        assert statuses.count("sold") == 2
        assert statuses.count("not_sold") == 1
        assert statuses.count("canceled") == 1

    def test_empty_message_returns_empty_list(self):
        assert parse_results_message("") == []
        assert parse_results_message("No results here\nJust noise") == []

    def test_lot_numbers_preserved(self):
        msg = "X999, Porsche Cayenne 17000€ sold"
        results = parse_results_message(msg)
        assert len(results) == 1
        assert results[0].lot_number == "X999"


# ── Model normalization ───────────────────────────────────────────────────────

class TestNormalizeModel:
    def test_exact_match(self):
        assert normalize_model("bmw m3") == "BMW M3"
        assert normalize_model("Toyota GT86") == "Toyota GT86"
        assert normalize_model("nissan gt-r") == "Nissan GT-R"

    def test_fuzzy_match_case_insensitive(self):
        assert normalize_model("BMW M3 Coupe") == "BMW M3"
        assert normalize_model("NISSAN GTR") == "Nissan GT-R"

    def test_unknown_model_capitalizes(self):
        result = normalize_model("some unknown car xyz")
        assert result == result.title() or result[0].isupper()

    def test_empty_string_doesnt_crash(self):
        result = normalize_model("")
        assert isinstance(result, str)

    def test_porsche_variants(self):
        # Carrera = finition de base du 911 → conservée pour distinguer des Turbo/GT3
        assert normalize_model("porsche 911 carrera") == "Porsche 911 Carrera"
        assert normalize_model("porsche cayman s") == "Porsche Cayman"
