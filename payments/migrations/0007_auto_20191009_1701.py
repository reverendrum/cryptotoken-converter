# Generated by Django 2.2.6 on 2019-10-09 17:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0006_coin_symbol_id_20190706_1521'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coin',
            name='symbol_id',
            field=models.CharField(blank=True, max_length=30, verbose_name='Native Coin Symbol (e.g. BTC)'),
        ),
        migrations.AlterField(
            model_name='conversion',
            name='deposit',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='conversion', to='payments.Deposit'),
        ),
        migrations.AlterField(
            model_name='conversion',
            name='from_coin',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversions_from', to='payments.Coin', verbose_name='From Coin'),
        ),
        migrations.AlterField(
            model_name='conversion',
            name='to_coin',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversions_to', to='payments.Coin', verbose_name='Converted Into (Symbol)'),
        ),
        migrations.AlterField(
            model_name='deposit',
            name='coin',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deposits', to='payments.Coin'),
        ),
    ]