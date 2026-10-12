"""Focused contract checks for schema-v2 structured retrieval."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import unittest
import uuid
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from iconctl import search_icons


IDS = {
    "fire_shield": "icon_11111111-1111-4111-8111-111111111111",
    "ice_shield": "icon_22222222-2222-4222-8222-222222222222",
    "ice_sword": "icon_33333333-3333-4333-8333-333333333333",
    "key": "icon_44444444-4444-4444-8444-444444444444",
    "other_shield": "icon_55555555-5555-4555-8555-555555555555",
}


class SearchRetrievalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.profile = json.loads((PACKAGE / "tools" / "search_profile_v1.json").read_text())
        self.profile["seed"]["max_document_frequency_ratio"] = 1.0
        columns = ",".join(self.profile["fts_columns"])
        self.connection.executescript(f"""
PRAGMA user_version=2;
CREATE TABLE icon(icon_id TEXT PRIMARY KEY,title TEXT,collection TEXT,ordinal TEXT,
 preferred_role TEXT,lifecycle_status TEXT,description TEXT);
CREATE TABLE rendition(icon_id TEXT,stable_role TEXT);
CREATE TABLE search_profile(profile_id TEXT PRIMARY KEY,profile_sha256 TEXT,profile_json TEXT);
CREATE VIRTUAL TABLE icon_fts USING fts5({columns}, tokenize='porter unicode61 remove_diacritics 2');
""")
        profile_json = json.dumps(self.profile, sort_keys=True, separators=(",", ":"))
        self.connection.execute("INSERT INTO search_profile VALUES(?,?,?)", (
            self.profile["profile_id"], hashlib.sha256(profile_json.encode()).hexdigest(), profile_json))
        self.add_icon("fire_shield", "Fire Shield", "shield", "fire", "red", "flaming guard")
        self.add_icon("ice_shield", "Ice Shield", "shield", "frost", "blue", "frozen guard")
        self.add_icon("ice_sword", "Ice Sword", "sword", "ice", "blue", "frozen blade")
        self.add_icon("key", "Golden Key", "key", "sparkle", "golden", "ornate key")
        self.add_icon("other_shield", "Other Shield", "shield", "frost", "blue", "frozen guard")
        self.connection.executescript("""
CREATE VIRTUAL TABLE icon_fts_vocab USING fts5vocab(icon_fts, 'row');
CREATE VIRTUAL TABLE icon_fts_instance USING fts5vocab(icon_fts, 'instance');
""")

    def add_icon(self, name: str, title: str, subject: str, effect: str,
                 color: str, description: str) -> None:
        icon_id = IDS[name]
        self.connection.execute("INSERT INTO icon VALUES(?,?,?,?,?,?,?)",
                                (icon_id, title, "Test", name, "default", "active", description))
        self.connection.execute("INSERT INTO rendition VALUES(?,?)", (icon_id, "default"))
        values = {
            "icon_id": icon_id, "subject": subject, "action": "", "state": "",
            "effect": effect, "symbol": "", "color": color, "material": "metal",
            "visible_text": "", "keywords": description, "description": description,
            "inferred_use": "defense" if "shield" in name else "", "composition": "centered",
            "title": title, "collection": "Test",
        }
        columns = self.profile["fts_columns"]
        self.connection.execute(
            f"INSERT INTO icon_fts({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
            tuple(values[column] for column in columns))

    def test_typed_constraints_aliases_and_stable_ties(self) -> None:
        result = search_icons(self.connection, require={"subject": ["shield"], "effect": ["ice"]},
                              limit=10)
        self.assertEqual([IDS["ice_shield"], IDS["other_shield"]],
                         [row["icon_id"] for row in result["results"]])
        self.assertEqual("constrained_browse", result["result_source"])
        self.assertEqual(8, result["shortfall"])

    def test_seed_requirement_precedence_and_exclusion(self) -> None:
        result = search_icons(self.connection, like=IDS["fire_shield"],
                              require={"subject": ["shield"], "effect": ["ice"]},
                              except_ids=[IDS["fire_shield"]], limit=2)
        self.assertEqual([IDS["ice_shield"], IDS["other_shield"]],
                         [row["icon_id"] for row in result["results"]])
        self.assertNotIn("effect", {term["field"] for term in result["seed_terms"]})
        self.assertTrue(all(IDS["fire_shield"] != row["icon_id"] for row in result["results"]))

    def test_explicit_fts_uses_sqlite_grammar_and_rejects_unknown_fields(self) -> None:
        result = search_icons(self.connection, query="subject:shields NOT effect:fire", limit=10)
        self.assertEqual([IDS["ice_shield"], IDS["other_shield"]],
                         [row["icon_id"] for row in result["results"]])
        with self.assertRaisesRegex(ValueError, "unsupported FTS field"):
            search_icons(self.connection, query="made_up:shield")
        with self.assertRaisesRegex(ValueError, "invalid FTS5 query"):
            search_icons(self.connection, query="subject:(shield OR")

    def test_large_exclusions_are_filtered_without_sql_placeholders(self) -> None:
        unknown = [f"icon_{uuid.uuid4()}" for _ in range(6249)]
        result = search_icons(self.connection, "frozen", except_ids=[IDS["ice_sword"], *unknown],
                              limit=2)
        self.assertEqual([IDS["ice_shield"], IDS["other_shield"]],
                         [row["icon_id"] for row in result["results"]])
        self.assertEqual("unknown_excluded_ids", result["diagnostics"][0]["code"])
        with self.assertRaisesRegex(ValueError, "malformed"):
            search_icons(self.connection, except_ids=["not-an-icon"])

    def test_text_and_seed_fuse_and_truthfully_report_shortfall(self) -> None:
        result = search_icons(self.connection, "missingword", like=IDS["fire_shield"], limit=100)
        self.assertEqual("seed_only_after_text_no_match", result["result_source"])
        self.assertTrue(any(item["code"] == "text_no_matches_used_seed_channel"
                            for item in result["diagnostics"]))
        self.assertEqual(100 - result["returned_count"], result["shortfall"])
        with self.assertRaisesRegex(LookupError, "seed not found"):
            search_icons(self.connection, like="icon_99999999-9999-4999-8999-999999999999")

    def test_seed_with_no_eligible_terms_does_not_turn_into_browse(self) -> None:
        columns = self.profile["fts_columns"]
        self.connection.execute("DELETE FROM icon_fts WHERE icon_id=?", (IDS["key"],))
        values = {column: "" for column in columns}
        values.update(icon_id=IDS["key"], subject="key", effect="sparkle", color="golden",
                      material="metal", keywords="icon", description="key", title="Golden Key",
                      collection="Test")
        self.connection.execute(
            f"INSERT INTO icon_fts({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
            tuple(values[column] for column in columns))
        result = search_icons(
            self.connection, like=IDS["key"],
            require={"subject": ["key"], "effect": ["sparkle"],
                     "color": ["gold"], "material": ["metal"]})
        self.assertEqual([], result["results"])
        self.assertEqual("seed_no_terms", result["result_source"])
        self.assertEqual("seed_has_no_eligible_terms", result["diagnostics"][0]["code"])

    def test_limit_bounds_all_excluded_and_logical_deduplication(self) -> None:
        for invalid in (0, 101, True):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "limit"):
                search_icons(self.connection, limit=invalid)
        self.connection.execute("INSERT INTO rendition VALUES(?,?)", (IDS["ice_shield"], "transparent"))
        result = search_icons(
            self.connection, "frozen",
            except_ids=[IDS["ice_shield"], IDS["ice_sword"], IDS["other_shield"]], limit=100)
        self.assertEqual([], result["results"])
        self.assertEqual(100, result["shortfall"])

    def test_explicit_query_does_not_turn_an_empty_seed_into_browse(self) -> None:
        columns = self.profile["fts_columns"]
        self.connection.execute("DELETE FROM icon_fts WHERE icon_id=?", (IDS["key"],))
        values = {column: "" for column in columns}
        values.update(icon_id=IDS["key"], subject="key", description="key",
                      title="Golden Key", collection="Test")
        self.connection.execute(
            f"INSERT INTO icon_fts({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
            tuple(values[column] for column in columns))
        result = search_icons(self.connection, query="subject:key", like=IDS["key"],
                              require={"subject": ["key"]})
        self.assertEqual([], result["results"])
        self.assertEqual("seed_no_terms", result["result_source"])


if __name__ == "__main__":
    unittest.main()
