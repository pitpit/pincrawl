import unittest
import json
from pincrawl.extractors.json_extractor import JsonExtractor


class TestJsonExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = JsonExtractor()
        self.sample_json = json.dumps(
            {
                "title": "Vintage Guitar",
                "price": {"value": 1500, "currency": "USD"},
                "location": {"city": "Nashville"},
                "details": {"brand": "Gibson", "year": 1960, "model": "Les Paul"},
            }
        )
        self.options = {
            "map": {
                "ad": {
                    "title": ".title",
                    "amount": ".price.value",
                    "currency": ".price.currency",
                    "city": ".location.city",
                },
                "product": {
                    "manufacturer": ".details.brand",
                    "year": ".details.year",
                    "name": ".details.model",
                },
            }
        }

    def test_extract_success(self):
        ad_info, product_info = self.extractor.extract(self.sample_json, self.options)

        self.assertEqual(ad_info.get("title"), "Vintage Guitar")
        self.assertEqual(ad_info.get("amount"), 1500)
        self.assertEqual(ad_info.get("currency"), "USD")
        self.assertEqual(ad_info.get("city"), "Nashville")

        self.assertIsNotNone(product_info)
        self.assertEqual(product_info.get("manufacturer"), "Gibson")
        self.assertEqual(product_info.get("year"), 1960)
        self.assertEqual(product_info.get("name"), "Les Paul")

    def test_extract_partial_data(self):
        # JSON missing some fields
        partial_json = json.dumps({"title": "Just a title", "price": {"value": 100}})

        ad_info, product_info = self.extractor.extract(partial_json, self.options)

        self.assertEqual(ad_info.get("title"), "Just a title")
        self.assertEqual(ad_info.get("amount"), 100)
        self.assertIsNone(ad_info.get("currency"))
        self.assertIsNone(product_info)

    def test_extract_no_product_map(self):
        options_no_prod = {"map": {"ad": {"title": ".title"}}}
        ad_info, product_info = self.extractor.extract(
            self.sample_json, options_no_prod
        )

        self.assertEqual(ad_info.get("title"), "Vintage Guitar")
        self.assertIsNone(product_info)

    def test_invalid_json(self):
        with self.assertRaises(ValueError) as cm:
            self.extractor.extract("{invalid json", self.options)
        self.assertIn("Invalid JSON", str(cm.exception))

    def test_invalid_jq_expression(self):
        # jq might raise ValueError or compile error depending on the bad expression
        # but the extractor catches ValueError during execution,
        # however jq.compile raises ValueError immediately for bad syntax.
        # The current implementation catches exceptions during execution loop,
        # but let's see what happens if compile fails.
        bad_options = {"map": {"ad": {"title": ".[[[bad syntax"}}}
        # jq.compile raises ValueError on invalid syntax
        with self.assertRaises(ValueError):
            self.extractor.extract(self.sample_json, bad_options)


if __name__ == "__main__":
    unittest.main()
