import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.models.titul import Titul
from app.models.test import Test

def inspect():
    settings = get_settings()
    engine = create_engine(settings.sync_database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        t = db.query(Titul).filter(Titul.uuid == "d2605e92-1d2f-4c85-9f9e-90650e4243cb").first()
        if not t:
            print("Titul not found")
            return
        print(f"Titul ID: {t.id}")
        print(f"Titul UUID: {t.uuid}")
        print(f"Titul Student ID: {t.student_id}")
        print(f"Titul Test ID: {t.test_id}")
        
        test = db.query(Test).filter(Test.id == t.test_id).first()
        if test:
            print(f"Test ID: {test.id}")
            print(f"Test Title: {test.title}")
            print(f"Test Question Count: {test.question_count}")
            print(f"Test Answer Key: {test.answer_key}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect()
