import csv
import io
import os

import pytest

from backend.app.data.loader import SAMPLE_DIRECTORY, load_books_from_uploads

# Agents build a model client on construction; tests never call it.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")


@pytest.fixture
def sample_files():
    return {
        name: (SAMPLE_DIRECTORY / name).read_text()
        for name in ["business.json", "transactions.csv", "jobs.csv", "invoices.csv"]
    }


@pytest.fixture
def books(sample_files):
    return load_books_from_uploads(sample_files)


@pytest.fixture
def change_csv():
    def change(files, filename, mutate):
        result = files.copy()
        reader = csv.DictReader(io.StringIO(files[filename]))
        fields = reader.fieldnames
        rows = list(reader)
        mutate(rows)
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        result[filename] = stream.getvalue()
        return result

    return change
