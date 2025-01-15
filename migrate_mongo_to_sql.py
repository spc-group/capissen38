#!/bin/env python
import logging
import sys
import argparse
from collections import OrderedDict

from pymongo import MongoClient
from pymongo.errors import CursorNotFound
from tqdm import tqdm
from tiled.client import from_uri
from bluesky.callbacks.tiled_writer import TiledWriter

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(
        prog='mongo2sql',
        description='Migrate mongo database to SQL database one document at a time',
    )
    parser.add_argument('mongo_uri')
    parser.add_argument("tiled_uri")
    parser.add_argument("--api-key", help="Tiled API key")
    parser.add_argument("-n", "--dry-run", help="Do not actually commit documents to the new database.", action="store_true")
    args = parser.parse_args()
    # Prepare the database objects
    mongo_client = MongoClient(args.mongo_uri)
    mongo_db = mongo_client[args.mongo_uri.rsplit("/", 1)[-1]]
    tiled_server, tiled_catalog = args.tiled_uri.rsplit("/", 1)
    tiled_client = from_uri(tiled_server, api_key=args.api_key)
    tiled_writer = TiledWriter(tiled_client[tiled_catalog])
    # Write the documents
    # ['run_start', 'event', 'run_stop', 'event_descriptor', 'resource', 'datum']
    collections = OrderedDict({
        "run_start": "start",
        "event_descriptor": "descriptor",
        "resource": "resource",
        "event": "event",
        "datum": "datum",
        "run_stop": "stop",
    })
    for coll_name, doc_name in collections.items():
        coll = mongo_db.get_collection(coll_name)
        docs =  coll.find()
        prog = tqdm(total=coll.estimated_document_count(), desc=coll_name, unit="doc")
        num_failures = 0
        while True:
            try:
                doc = next(docs)
            except StopIteration:
                break
            except CursorNotFound as exc:
                num_failures += 1
            finally:
                prog.update()
            doc.pop("_id", None)
            # Commit the document to Tiled
            if not args.dry_run:
                try:
                    tiled_writer(doc_name, doc)
                except Exception as exc:
                    num_failures += 1
                    continue
        # Reporting
        print(f"{coll_name} failed: {num_failures}")

if __name__ == "__main__":
    main()
