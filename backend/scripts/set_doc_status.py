"""
Mark an indexed document "archived" (docs for an old version: retrieval skips it unless the question asks about an
older version) or "current".

  python scripts/set_doc_status.py novacloud_sdk_v2_archived archived
  python scripts/set_doc_status.py --list
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from app.services.retrieval.vector_store import VectorStoreService


def main() -> int:
    store = VectorStoreService()
    if sys.argv[1:] == ["--list"]:
        for doc in store.get_all_documents():
            print(f"{doc['doc_id']:<36} {doc.get('status', 'current'):<9} {doc['filename']}")
        return 0
    if len(sys.argv) != 3 or sys.argv[2] not in ("archived", "current"):
        print(__doc__)
        return 1
    if not store.set_document_status(sys.argv[1], sys.argv[2]):
        print(f"No document with id {sys.argv[1]} (see --list)")
        return 1
    print(f"{sys.argv[1]} is now {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
