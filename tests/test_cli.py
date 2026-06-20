from typer.testing import CliRunner

from cli import app


def test_list_command_registers() -> None:
    result = CliRunner().invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Endpoints" in result.output
    assert "Capabilities" in result.output
