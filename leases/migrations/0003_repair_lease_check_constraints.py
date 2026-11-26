from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("leases", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE leases_lease
                ADD CONSTRAINT lease_monthly_rent_positive
                CHECK (monthly_rent > 0)
            """,
            reverse_sql="""
                ALTER TABLE leases_lease
                DROP CHECK lease_monthly_rent_positive
            """,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE leases_lease
                ADD CONSTRAINT lease_deposit_nonnegative
                CHECK (security_deposit >= 0)
            """,
            reverse_sql="""
                ALTER TABLE leases_lease
                DROP CHECK lease_deposit_nonnegative
            """,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE leases_lease
                ADD CONSTRAINT lease_billing_day_valid
                CHECK (billing_day >= 1 AND billing_day <= 28)
            """,
            reverse_sql="""
                ALTER TABLE leases_lease
                DROP CHECK lease_billing_day_valid
            """,
        ),
    ]
