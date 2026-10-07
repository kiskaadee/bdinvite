from dataclasses import dataclass, field


@dataclass(frozen=True)
class Identity:
    """Domain model representing a validated authenticated principal.

    Identity Origin Integrity:
    Instances of Identity must only represent verified authentication results produced
    by an authentication adapter or port, and must never be constructed directly from
    raw unvalidated client headers or requests.
    """

    subject: str
    email: str
    name: str | None = None
    groups: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("Identity subject must be a non-empty string")
        if not isinstance(self.email, str) or not self.email.strip():
            raise ValueError("Identity email must be a non-empty string")
        if self.name is not None and not isinstance(self.name, str):
            raise TypeError("Identity name must be a string or None")
        if not isinstance(self.groups, (list, tuple)):
            raise TypeError("Identity groups must be a list of strings")
        for g in self.groups:
            if not isinstance(g, str):
                raise TypeError("Identity groups items must be strings")
        object.__setattr__(self, "groups", list(self.groups))

    def has_group(self, group: str) -> bool:
        """Check if the identity belongs to a specific group."""
        return group in self.groups
