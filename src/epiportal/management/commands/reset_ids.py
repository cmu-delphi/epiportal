from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import connection


class Command(BaseCommand):
    help = "Reset AUTO_INCREMENT values for all database tables based on current max IDs"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made\n"))
        
        models_processed = 0
        models_skipped = 0
        
        # Get all models from installed apps
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                # Skip proxy models (they use the same table as their parent)
                if model._meta.proxy:
                    continue
                
                # Skip models without a primary key or with non-auto-increment PK
                pk_field = model._meta.pk
                if not pk_field or not pk_field.auto_created:
                    continue
                
                table_name = model._meta.db_table
                
                try:
                    with connection.cursor() as cursor:
                        # Get the current max ID
                        cursor.execute(f"SELECT MAX(`{pk_field.column}`) FROM `{table_name}`")
                        result = cursor.fetchone()
                        max_id = result[0] if result[0] is not None else 0
                        
                        # Calculate the next AUTO_INCREMENT value
                        next_auto_increment = max_id + 1 if max_id > 0 else 1
                        
                        if dry_run:
                            self.stdout.write(
                                f"Would reset {model._meta.label}: "
                                f"table `{table_name}` AUTO_INCREMENT to {next_auto_increment} "
                                f"(current max ID: {max_id})"
                            )
                        else:
                            # Reset AUTO_INCREMENT
                            cursor.execute(
                                f"ALTER TABLE `{table_name}` AUTO_INCREMENT = {next_auto_increment}"
                            )
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Reset {model._meta.label}: "
                                    f"table `{table_name}` AUTO_INCREMENT to {next_auto_increment} "
                                    f"(current max ID: {max_id})"
                                )
                            )
                        
                        models_processed += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error processing {model._meta.label} ({table_name}): {str(e)}"
                        )
                    )
                    models_skipped += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted: {models_processed} tables processed"
            )
        )
        if models_skipped > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"{models_skipped} tables skipped due to errors"
                )
            )

