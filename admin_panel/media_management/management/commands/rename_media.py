from pathlib import Path

import media_management.management.commands._media_manager as media_manager
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

DEFAULT_MEDIA_PATH: str = "./media/"


class Command(BaseCommand):
    help = "Remove unused files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--media-path",
            help=f"The path to the media folder."
            f"If not provided, {DEFAULT_MEDIA_PATH} is used.",
        )

        parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm renaming")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            self.rename_media(*args, **options)
        except KeyboardInterrupt:
            self.stdout.write(self.style.ERROR("Renaming cancelled."))

    def rename_media(self, *args, **options):
        media_path = Path(options.get("media_path") or DEFAULT_MEDIA_PATH)
        if not media_path.exists():
            raise CommandError("Provided media-path does not exist.")

        medias = media_manager.all_media()

        to_rename: dict[Path, Path] = {}

        for model_instance, model_image, media_attr in medias:
            file = Path(model_image).absolute()

            model_type = type(model_instance).__name__
            model_name = getattr(model_instance, "name", None) or getattr(
                model_instance, "country"
            )
            target = file.parent / f"{model_type}_{model_name}_{media_attr}{file.suffix}"

            if target.exists():
                self.stderr.write(f"{target.name} already exists! Can't rename {file.name}")
                continue

            to_rename[file] = target
            self.stdout.write(f"Will rename {file.name} to {target.name}")

        self.stdout.write("")
        if not options["yes"] and not media_manager.boolean_input(
            f"Rename {len(to_rename)} files? This will not erase existing files.", default=True
        ):
            self.stdout.write(self.style.ERROR("Renaming cancelled."))
            return

        if to_rename:
            for source, target in to_rename.items():
                source.rename(target)

            self.stdout.write(self.style.SUCCESS("Files renamed!"))

            for model_instance, model_image, media_attr in medias:
                model_image_path = model_image.absolute()
                if model_image_path in to_rename:
                    model_image_field = getattr(model_instance, media_attr)
                    new_path = to_rename[model_image_path]

                    # Django won't take a non-relative path here
                    model_image_field.name = str(new_path.relative_to(media_path.absolute()))
                    model_instance.save()

            self.stdout.write(self.style.SUCCESS("Database updated!"))
