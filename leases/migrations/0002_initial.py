import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('leases', '0001_initial'),
        ('properties', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # Add tenant_id first, then create its foreign-key constraint separately.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name='lease',
                    name='tenant',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='leases',
                        to='tenants.tenant',
                        db_constraint=False,
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE `leases_lease` "
                        "ADD CONSTRAINT "
                        "`leases_lease_tenant_id_cd1b7627_fk_tenants_tenant_id` "
                        "FOREIGN KEY (`tenant_id`) REFERENCES `tenants_tenant` (`id`)"
                    ),
                    reverse_sql=(
                        "ALTER TABLE `leases_lease` "
                        "DROP FOREIGN KEY "
                        "`leases_lease_tenant_id_cd1b7627_fk_tenants_tenant_id`"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='lease',
                    name='tenant',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='leases',
                        to='tenants.tenant',
                    ),
                ),
            ],
        ),

        # Add unit_id first, then create its foreign-key constraint separately.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name='lease',
                    name='unit',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='leases',
                        to='properties.rentalunit',
                        db_constraint=False,
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE `leases_lease` "
                        "ADD CONSTRAINT "
                        "`leases_lease_unit_id_03804e5a_fk_properties_rentalunit_id` "
                        "FOREIGN KEY (`unit_id`) REFERENCES `properties_rentalunit` (`id`)"
                    ),
                    reverse_sql=(
                        "ALTER TABLE `leases_lease` "
                        "DROP FOREIGN KEY "
                        "`leases_lease_unit_id_03804e5a_fk_properties_rentalunit_id`"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='lease',
                    name='unit',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='leases',
                        to='properties.rentalunit',
                    ),
                ),
            ],
        ),

        migrations.AddIndex(
            model_name='lease',
            index=models.Index(
                fields=['unit', 'status'],
                name='lease_unit_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='lease',
            index=models.Index(
                fields=['tenant', 'status'],
                name='lease_tenant_status_idx',
            ),
        ),
        migrations.AddConstraint(
            model_name='lease',
            constraint=models.CheckConstraint(
                condition=models.Q(('monthly_rent__gt', 0)),
                name='lease_monthly_rent_positive',
            ),
        ),
        migrations.AddConstraint(
            model_name='lease',
            constraint=models.CheckConstraint(
                condition=models.Q(('security_deposit__gte', 0)),
                name='lease_deposit_nonnegative',
            ),
        ),
        migrations.AddConstraint(
            model_name='lease',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ('billing_day__gte', 1),
                    ('billing_day__lte', 28),
                ),
                name='lease_billing_day_valid',
            ),
        ),
    ]
