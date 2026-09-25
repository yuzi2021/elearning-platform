"""Load the deterministic fictional demonstration dataset."""
from pathlib import Path
import runpy

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or refresh the deterministic eLearning demonstration data."

    def handle(self, *args, **options):
        # Preserve the coursework seed script as the single source of records
        # while exposing it through Django's standard operational interface.
        seed_script = Path(settings.BASE_DIR) / "load_demo_data.py"
        runpy.run_path(str(seed_script), run_name="__main__")
        self.stdout.write(self.style.SUCCESS("Demo dataset is ready."))
