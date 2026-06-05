import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.models.attempt import Attempt
from app.models.titul import Titul
from app.models.student import Student
from app.models.test import Test

def list_attempts():
    settings = get_settings()
    engine = create_engine(settings.sync_database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        attempts = db.query(Attempt).order_by(Attempt.created_at.desc()).limit(15).all()
        print(f"Total attempts: {db.query(Attempt).count()}")
        for att in attempts:
            titul = db.query(Titul).filter(Titul.id == att.titul_id).first()
            student_name = "Unknown"
            test_title = "Unknown"
            if titul:
                student = db.query(Student).filter(Student.id == titul.student_id).first()
                if student:
                    student_name = student.full_name
                test = db.query(Test).filter(Test.id == titul.test_id).first()
                if test:
                    test_title = test.title
                    
            print(f"ID: {att.id} | Student: {student_name} | Test: {test_title} | Score: {att.score}/{att.total} | Status: {att.status} | Needs Review: {att.needs_review}")
            print(f"  Source file: {att.source_file}")
            print(f"  Debug file: {att.debug_file}")
            print(f"  Detected (first 5): {dict(list(att.detected.items())[:5]) if att.detected else {}}")
            print("-" * 50)
    finally:
        db.close()

if __name__ == "__main__":
    list_attempts()
