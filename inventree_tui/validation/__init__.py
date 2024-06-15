from textual.validation import ValidationResult, Validator

class GreaterThan(Validator):
    def __init__(self, value: float | int):
        super().__init__()
        self.value = value

    def validate(self, value: str) -> ValidationResult:
        def is_greater_than(value: str) -> bool:
            if len(value) == 0:
                return True
            return float(value) > self.value
        return self.success() if is_greater_than(value) else self.failure(f"Not greater than {self.value}")
