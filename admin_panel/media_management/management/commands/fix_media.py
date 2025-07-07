from bd_models.models import Ball, Economy, Regime, Special

model_fields = {
    Ball: ["collection_card", "wild_card"],
    Special: ["background"],
    Economy: ["icon"],
    Regime: ["background"],
}

to_return = ""

for model, fields in model_fields.items():
    for obj in model.objects.all():
        for field in fields:
            f = getattr(obj, field)
            if f.name.startswith('/'):
                f.name = f.name.lstrip('/')
                setattr(obj, field, f)
                obj.save()
                to_return += f"\nFixed: {model.__name__} ID {obj.pk} field {field} to {f.name}"

print(to_return)

