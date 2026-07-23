from django import template


register = template.Library()


@register.inclusion_tag('tailwind_forms/formfield.html')
def tailwind_formfield(formfield, implicit=False):
    # we just monkey-patch the class attr. if (i.e. as long as) it works, it ain't stupid
    if not formfield:
        return {"formfield": None}

    if formfield.field.disabled:
        formfield.field.widget.attrs['class'] = "bg-sunken text-ink-muted border border-edge cursor-not-allowed"
    elif formfield.errors:
        formfield.field.widget.attrs['class'] = (
            "bg-critical-wash text-ink border border-critical focus:border-critical focus:ring-critical-wash")
    else:
        formfield.field.widget.attrs['class'] = (
            "bg-surface text-ink border border-edge focus:border-accent focus:ring-accent-wash")
    formfield.field.widget.attrs['class'] += " text-sm rounded-md h-10 px-3 py-2 w-full"

    if implicit:
        formfield.field.widget.attrs['placeholder'] = formfield.label

    return {
        'formfield': formfield,
        'implicit': implicit,
    }


@register.inclusion_tag('tailwind_forms/formfield.html')
def tailwind_formfield_implicit(formfield):
    # implicit meaning: the label is rendered as a placeholder. This only works for text inputs and fire-once (i.e. the
    # first time the form is rendered)
    return tailwind_formfield(formfield, True)
