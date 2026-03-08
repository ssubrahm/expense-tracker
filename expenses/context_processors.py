def user_context(request):
    """Add is_family_admin and current_member to all templates."""
    member = None
    is_admin = False
    if request.user.is_authenticated:
        member = getattr(request.user, "family_member", None)
        is_admin = (member and member.is_family_admin) or request.user.is_superuser
    return {
        "current_member": member,
        "is_family_admin": is_admin,
    }
