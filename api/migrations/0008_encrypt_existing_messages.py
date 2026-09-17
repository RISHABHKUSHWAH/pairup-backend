from django.db import migrations


def encrypt_existing_messages(apps, schema_editor):
    Message = apps.get_model('api', 'Message')
    from api.crypto import encrypt_text, CIPHER_PREFIX
    
    count = 0
    for msg in Message.objects.all():
        if msg.body and not msg.body.startswith(CIPHER_PREFIX):
            msg.body = encrypt_text(msg.body)
            msg.save(update_fields=['body'])
            count += 1
    if count > 0:
        print(f" [Migration] Encrypted {count} existing chat message(s).")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_message_deleted_by_receiver_and_more'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing_messages, reverse_code=noop_reverse),
    ]
