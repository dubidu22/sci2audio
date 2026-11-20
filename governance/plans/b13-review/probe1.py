import sys; sys.path.insert(0, "tests/unit")
from test_layout import *
pages = [page_with_head(n, None) for n in range(1, 11)]
for n in (2, 3, 4):
    pages[n - 1] = small_header_page(n, below=14)
doc = build_document(content(*pages))
print("furniture:", texts(doc, BlockKind.FURNITURE), "text count:", texts(doc).count("Model Accuracy F1"))
