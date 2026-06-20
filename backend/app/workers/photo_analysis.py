from app.services.photo_analysis_service import run_photo_analysis


def analyze_photos_job(files_data: list[dict], user_id: int) -> dict:
    return run_photo_analysis(files_data=files_data, user_id=user_id)
