#!/usr/bin/env python3
"""Write the visually authored, exposed search-development set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


LITERAL = [
    ("two white daisies with yellow centers", "icon_3777dd52-7475-4e28-9b6c-769596f6571b",
     ["two daisy-like flowers", "white petals", "yellow centers"]),
    ("gold rimmed bowl spilling purple liquid", "icon_79c693a5-3aab-46cd-8134-edc0883387b3",
     ["open bowl or vessel", "purple liquid spilling over the rim", "gold rim"]),
    ("brown leather chest armor with silver scales", "icon_f9c11d84-fac3-4f2e-af2f-c126e1aff1c5",
     ["torso armor", "brown leather", "silver scale panel"]),
    ("long red arrow with hollow black triangular head", "icon_231ff884-b66e-4c8c-95de-9ed8c916ae85",
     ["single long arrow", "reddish shaft", "hollow triangular metal head"]),
    ("dark double headed axe with green glowing cutouts", "icon_6ae98114-7e88-4e70-a87c-e55e7ae4fc04",
     ["double-bladed axe", "dark metal head", "green glowing cutouts"]),
    ("ornate gold belt with red round gem and leaf clasp", "icon_85de6748-a4d9-46f1-ae88-6918b15ef889",
     ["ornamental belt", "round red gem", "gold leaf-shaped clasp"]),
    ("single heart shaped dark red berry with green leaves and curled stem", "icon_7cdf1da1-9cbf-44b9-a59f-ca6a8178ad64",
     ["single heart-shaped berry", "dark red fruit", "green leaves", "curled stem"]),
    ("layered curved purple bone spikes with pink sparks", "icon_9f2450b6-91e1-4215-b317-29ce5f9c3880",
     ["several layered curved pointed forms", "purple color", "pink specks or sparks"]),
    ("closed blue book with purple crystal on the cover", "icon_a1a69275-f64b-457e-b066-c54168e063ca",
     ["closed blue book", "large purple crystal on cover", "gold trim"]),
    ("pair of tall brown leather boots with pale laces", "icon_ca46f383-6b9e-4fdc-86fb-9922aaaf6db4",
     ["pair of tall boots", "brown leather", "pale laces"]),
    ("red recurve bow with hooked ends and no arrow", "icon_6facc46c-9762-491a-b93c-bf00c3b7d027",
     ["single strung bow", "red limbs", "hooked ends", "no arrow"]),
    ("cinnamon sticks with star anise and red peppercorns", "icon_a0da1a65-114c-41f7-925a-7dab1f6ac082",
     ["rolled cinnamon sticks", "star-shaped spice pods", "small red peppercorns"]),
    ("glossy rectangular red metal ingot with grooves", "icon_633bb651-2795-471b-9bd2-46180094958f",
     ["single rectangular ingot", "glossy red material", "parallel grooves"]),
    ("three gold oval discs on a knotted brown cord", "icon_6fa88ca0-4d95-4a4d-96ca-98965b5cacb3",
     ["three gold oval discs", "openings through discs", "knotted reddish-brown cord"]),
    ("three glowing green and blue curved dagger blades", "icon_c9937b2b-69a1-43cb-b3a6-77eb341f33c3",
     ["three separate curved blades", "green and blue glow"]),
    ("pale egg covered in vines beside red glowing mushrooms", "icon_5fc5e89c-931c-4c36-a7bf-ba5a45314aa2",
     ["large pale egg-shaped form", "green vines and leaves", "red-orange glowing mushrooms"]),
    ("angular glass bottle of blue liquid with gold bands", "icon_a809d645-a331-433a-8f77-41255572bbd3",
     ["angular glass bottle", "blue liquid", "gold bands and stopper"]),
    ("blue metal hoe head on a wooden handle", "icon_0ed16b9a-6d99-4b8e-b1eb-e2521d4b76cc",
     ["handheld hoe", "blue metal head", "wooden handle"]),
    ("closed purple flower bud with green leaves", "icon_6c9cb6a6-8d3a-4725-95dc-784715369147",
     ["closed flower bud", "purple overlapping petals", "green leaves"]),
    ("stack of pancakes with syrup and butter on a white plate", "icon_6bfc4259-24a0-4bd7-bc91-bcfe9014ead5",
     ["stacked pancakes", "syrup", "butter pat", "white plate"]),
    ("deep red apple with one cut half and black seeds", "icon_6845399f-15bc-4a46-825f-9ff024169f43",
     ["one whole red apple", "one cut apple half", "visible dark seeds"]),
    ("pair of white gloves with gold metal cuffs", "icon_2dcee046-90bb-427d-8dca-dab201cce0b6",
     ["pair of white gloves", "gold-and-silver forearm cuffs"]),
    ("closed purple helmet with ornate gold face guard", "icon_7f9b6f40-8dac-43d3-a9ad-4115f69ee919",
     ["closed-face helmet", "purple shell", "ornate gold face guard"]),
    ("pair of gold earrings with square pink gems", "icon_99d31109-001a-4f25-8b8f-fb0f73b3317b",
     ["pair of dangling earrings", "square pink gemstones", "gold settings"]),
    ("simple gold key with round bow and three teeth", "icon_b5283aa4-b7a3-4d99-98be-231957fd5a7d",
     ["single gold key", "round bow", "three teeth"]),
    ("blue crystal lance with six side spikes and cyan aura", "icon_9e4c7f97-7bfa-40d6-9f77-d850d54e2910",
     ["single spear-like weapon", "blue crystal point", "six side spikes", "cyan aura"]),
    ("cute blue slime blob with big dark eyes and a tiny mouth", "icon_67f9a32b-741a-4e5b-9b7d-e47576cafb3d",
     ["blue blob creature", "two large dark eyes", "tiny round mouth"]),
    ("necklace strung with white fangs and a pink shell charm", "icon_7a266323-b92a-4262-8b3a-cf83bdacda44",
     ["cord necklace", "several white fang-shaped pieces", "pink shell charm"]),
    ("gold necklace with large cyan diamond pendant in star frame", "icon_13499c39-983a-4f31-80a5-f6b28f91556e",
     ["gold necklace", "large cyan diamond-shaped pendant", "gold star-shaped frame"]),
    ("three red trumpet mushrooms with pale bumps", "icon_922acf5f-15d3-4615-816f-f2b2769d9985",
     ["three red trumpet-shaped growths", "pale rounded bumps"]),
    ("corked blue potion bottle inside a wooden barrel sleeve splashing liquid", "icon_3abe0053-0d97-4686-bd7a-3e9e479958e9",
     ["corked bottle", "blue liquid", "wooden barrel-like sleeve", "blue splash"]),
    ("beige oval stone rune carved with a simple person symbol", "icon_d7b85886-0e75-4f2f-986b-80e7aa48e159",
     ["oval beige stone", "dark carved person-like symbol"]),
    ("torn pale scroll with a hand drawn animal diagram and writing", "icon_f79aa98d-0e55-446d-ad3b-331332602ed8",
     ["torn pale sheet or scroll", "simple black animal diagram", "handwritten lines"]),
    ("mossy closed book with brown strap and gold angular clasp", "icon_b5cc489f-39d2-4fc9-ada5-ba375d4264f8",
     ["closed worn book", "green moss or slime", "brown strap", "gold angular clasp"]),
    ("irregular gray stone shield with cracks and bronze rivets", "icon_e61d1550-250d-4398-92b4-4d0755eb3e03",
     ["irregular gray shield or slab", "visible cracks", "many bronze rivets"]),
    ("purple and gold vortex with bright white center", "icon_90979818-e92d-4630-b41b-30e25bdbc74a",
     ["spiraling vortex", "purple and pale-gold bands", "bright white center"]),
    ("cyan glowing staff with three pronged crystal head", "icon_0b98bd96-375b-43c2-a103-ce0c61427785",
     ["single staff", "three-pronged crystal head", "cyan glow"]),
    ("curved silver sword with red spiked guard and wrapped handle", "icon_32786825-0fc3-46fd-8b76-460a2d74bf48",
     ["curved silver blade", "red spiked guard", "dark wrapped handle"]),
    ("bundle of green asparagus spears", "icon_42579385-7a52-47b9-abff-d9d8a9fc72d0",
     ["several green asparagus spears"]),
    ("single wing with red orange and yellow feathers", "icon_616f4d2b-50d7-422e-8ba6-65f17978700c",
     ["single feathered wing", "red and orange upper feathers", "yellow lower feathers"]),
]


FUNCTIONAL = [
    ("an icon for brewing a dangerous red potion", "icon_12933995-e44d-4c9b-b63f-728e969e5274",
     ["hand holding a flask", "red liquid"]),
    ("a fire arrow attack ability", "icon_c23434ce-0954-4a98-ab32-8b9e062cdb6a",
     ["arrow or arrowhead", "surrounding flames"]),
    ("a blacksmith forging equipment", "icon_39cd515d-4918-48d3-bcf2-86a381a80104",
     ["hammer striking an anvil", "forging sparks or glow"]),
    ("a buff that protects or increases carried gold", "icon_6b425c71-f4a1-4262-bbf7-0917f9efcab0",
     ["coin purse or money bag", "gold protective aura"]),
    ("pouring oil or sauce while cooking", "icon_48d2c9a7-1c0a-444b-b7b0-5c374127abc5",
     ["container pouring liquid", "golden cooking liquid"]),
    ("enchant a weapon with ice", "icon_2c9f951c-4c67-424d-a6d3-add94916722c",
     ["hand gripping a weapon", "ice coating or shards"]),
    ("acid damage or a corrosive splash", "icon_00511185-9b0d-48a9-be0f-63886f3bc4da",
     ["green liquid splash"]),
    ("poison bubbles rising from a toxic pool", "icon_aa9c8e10-e8d5-4686-9846-0c5b6a46dec3",
     ["green bubbles", "green toxic-looking pool"]),
    ("nature amulet or druid talisman", "icon_cd054255-a892-481d-b51b-bd5416fb6e2c",
     ["pendant or amulet", "green gem", "natural bone-like setting"]),
    ("mechanical crane lifting cargo", "icon_22cc8307-8afc-4e3a-8a52-28fa053874fb",
     ["mechanical claw", "wooden crate being lifted"]),
    ("repair or replace fishing line", "icon_233dc591-840a-46af-9b26-cdeebcae823c",
     ["spool", "coiled fishing line"]),
    ("ability to reveal hidden enemies everywhere", "icon_eed76164-38fc-4972-b056-63ebfbcc0167",
     ["many watching eyes", "magical field"]),
    ("area lightning explosion", "icon_4dbc28e1-e4ca-43bb-bc8b-84221965813e",
     ["lightning radiating in many directions", "bright central orb"]),
    ("martial artist blocking an attack", "icon_9544d9de-6a90-4986-a641-a53c35cdf9a2",
     ["martial artist", "crossed forearms in defensive stance"]),
    ("holy healing light", "icon_8335bca6-c9a1-4466-a29d-49a99ffadcf1",
     ["radiant golden orb or star", "downward golden beams"]),
    ("holy sword strike landing in a magic circle", "icon_9c0aa40e-5eb0-4508-ba9f-0d86e82cf37d",
     ["glowing blade or pillar striking downward", "gold rune circle"]),
    ("conjure a flame between both hands", "icon_97d6b1e3-51a7-4226-948e-083afdb917be",
     ["two hands", "central conjured flame"]),
    ("summon a destructive tornado", "icon_1d66dc41-8a7d-4955-b96a-4f21b14c8232",
     ["large tornado", "debris or destructive ground effect"]),
    ("throw several daggers at once", "icon_cf5be030-1f37-4117-8ad1-49b66c83f0a0",
     ["throwing hand", "three flying daggers"]),
    ("cursed claw transformation", "icon_3f53a08d-6631-4d67-9e36-fd3fdbef2e3f",
     ["large clawed hand", "blue supernatural flames"]),
]


SEEDS = [
    "icon_ffd6bc7a-7829-465b-8411-c0219d012e19", "icon_5b0a4f81-3313-4d65-9a21-7c5d985f41fa",
    "icon_a9f37a1d-29ee-4b77-a2c3-b9f456a9376b", "icon_0bda659c-f3c8-493d-bd90-43c7765b0c07",
    "icon_01cd8a62-d66f-4e30-9953-31f436d43c52", "icon_64ac80ea-85fb-41ef-90ae-e589e7365ba5",
    "icon_3352abb1-95e1-4425-bee6-bf825a86edcf", "icon_02b5379a-9f70-4317-9ce5-4791b3ae6b21",
    "icon_175f425d-c24a-4888-865d-2d5a27b48a82", "icon_0d515f04-0a86-4e0c-9d32-78e1e4ea2c59",
    "icon_073f576e-7373-4fa9-a04b-45a36ed87a75", "icon_71545550-430b-4608-8534-40274bcae646",
    "icon_5ad42913-e63b-4bb3-8320-82ab023296fd", "icon_a85ee120-e9bb-438d-adb3-9315dc9ccf5e",
    "icon_f7d3c3e4-3eae-4a1b-9fcd-f43aa8f8b44f", "icon_ca8508c1-a8af-4fea-b879-cdfe9686d8ad",
    "icon_b3d4aace-2d3d-46a4-9761-e5381f9d7e19", "icon_d4f1adac-90a1-45c8-b481-2b6075c2bda9",
    "icon_67d20777-3efc-476e-9d09-adb353dc5838", "icon_a8c05278-0225-43ea-8b25-a83d0af10fc9",
    "icon_a5f58b1f-61f7-456a-af48-893fe0506eb1", "icon_437464ea-5cde-4206-822a-bee3894b4928",
    "icon_19c62156-1274-485d-bd9b-79e7ff5e6e1a", "icon_9aa3976b-e792-416c-af08-ee94df5246e7",
    "icon_237393fd-a62e-4f82-ad63-7186425b5927", "icon_ce08b261-9939-4792-87d7-940eb7783eb2",
    "icon_a06e1a25-4bc4-440a-add6-7e5231d150e2", "icon_54885839-ef3d-4bfa-979e-7e1251ac67be",
    "icon_2c9eeddc-ac2c-4eef-abb7-25ce559abc99", "icon_85d2a090-c01d-403a-9046-493025453269",
]


SEED_TEXT = [
    "make it two white daisies with yellow centers",
    "same open bowl but spilling purple liquid",
    "brown leather armor with a silver scale panel",
    "red shaft with a hollow black triangular head",
    "double headed dark steel axe with bright green cutouts",
    "brown and gold leaf belt with a round red gem",
    "single heart shaped dark red berry with a curled stem",
    "layered purple curved bone forms with pink sparks",
    "blue book with a large purple crystal on the cover",
    "plain tall brown leather boots with pale laces",
    "red bow with hooked ends",
    "cinnamon sticks star anise and red peppercorns",
    "solid glossy rectangular red ingot",
    "three oval gold discs on a knotted brown cord",
    "three separate glowing green and blue blades",
    "pale egg covered with vines and red glowing mushrooms",
    "angular bottle with blue liquid and gold bands",
    "blue metal hoe head on a wooden handle",
    "closed purple flower bud",
    "pancakes with syrup and butter on a white plate",
    "deep purple red apple with one cut half and green leaves",
    "white gloves with gold cuffs",
    "closed purple helmet with ornate gold face guard",
    "square pink gemstone earrings",
    "simple straight gold key with round bow and three teeth",
    "crystal blue lance with six side spikes and cyan aura",
    "blue blob creature with big eyes and a tiny mouth",
    "necklace made of white fangs and a pink shell charm",
    "single cyan diamond pendant in a gold star frame",
    "three red trumpet mushrooms with pale bumps",
]


NEGATIVE = [
    ("shield", "glass"), ("bottle", "stone"), ("helmet", "glass"),
    ("two boots", "water"), ("closed book", "skin"), ("whole apple", "metal"),
    ("key", "water"), ("plant bud", "bone"), ("pancakes", "metal"),
    ("spear-like weapon", "paper"),
]


def case(case_id: str, family: str, request: dict, properties: list[str],
         suitable: list[str], notes: str) -> dict:
    return {
        "case_id": case_id,
        "family": family,
        "request": request,
        "required_visual_properties": properties,
        "optional_visual_properties": [],
        "known_suitable_ids": suitable,
        "notes": notes,
    }


def build() -> dict:
    if not (len(LITERAL) == 40 and len(FUNCTIONAL) == 20 and len(SEEDS) == len(SEED_TEXT) == 30
            and len(NEGATIVE) == 10):
        raise ValueError("development allocation changed")
    cases = [case(f"literal-{index:03}", "literal", {"text": text, "limit": 20},
                  properties, [target], "Target thumbnail visually inspected during authoring.")
             for index, (text, target, properties) in enumerate(LITERAL, 1)]
    for index, ((_, target, properties), seed, text) in enumerate(
            zip(LITERAL[:30], SEEDS, SEED_TEXT, strict=True), 1):
        cases.append(case(
            f"seed-{index:03}", "seed_modification",
            {"text": text, "like": seed, "except": [seed], "limit": 20},
            properties, [target],
            "Seed and target thumbnails visually inspected; target is reused from the literal family."))
    cases.extend(case(f"functional-{index:03}", "functional", {"text": text, "limit": 20},
                      properties, [target], "Accepted visual metaphor fixed during authoring.")
                 for index, (text, target, properties) in enumerate(FUNCTIONAL, 1))
    cases.extend(case(
        f"negative-{index:03}", "exclusion_negative",
        {"require": {"subject": [subject], "material": [material]}, "limit": 5},
        [subject, material], [],
        "Expected empty: both facet values exist in the catalog, but no icon asserts this combination.")
        for index, (subject, material) in enumerate(NEGATIVE, 1))
    if len({item["case_id"] for item in cases}) != 100:
        raise ValueError("development case IDs are not unique")
    return {
        "$schema": "../search-retrieval-v1/benchmark-schema-v2.json",
        "benchmark_schema_version": 2,
        "set_kind": "development",
        "author": "Codex visual development authoring; not independent",
        "exposure": "Authored after exposure to the v1 implementation and V4 failures; development tuning only.",
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    print(args.output)


if __name__ == "__main__":
    main()
