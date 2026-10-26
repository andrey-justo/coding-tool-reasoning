from pathlib import Path

from src.service.test_diagnostics import (
    JunitTestFailureParser,
    TestFailureContext,
    TestFailureParserResolver,
    TextTestFailureParser,
    TrxTestFailureParser,
    extract_failure_location,
)

_AKKA_STACK = (
    "   at Akka.Serialization.V2.Tests.AkkaSerializerGeneratorDiagnosticsSpec."
    "Should_not_report_AKKASG011_for_arrays() in "
    "C:\\repo\\src\\core\\Akka.Serialization.V2.Tests\\"
    "AkkaSerializerGeneratorDiagnosticsSpec.cs:line 343"
)

_TRX_DOCUMENT = f"""<?xml version="1.0" encoding="utf-8"?>
<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Results>
    <UnitTestResult testName="Akka.Serialization.V2.Tests.Spec.Passes" outcome="Passed" />
    <UnitTestResult testName="Akka.Serialization.V2.Tests.Spec.Fails" outcome="Failed">
      <Output>
        <ErrorInfo>
          <Message>Expected no AKKASG011 diagnostic but found one for int[].</Message>
          <StackTrace>{_AKKA_STACK}</StackTrace>
        </ErrorInfo>
      </Output>
    </UnitTestResult>
  </Results>
</TestRun>
"""

_JUNIT_DOCUMENT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest">
    <testcase classname="tests.test_app" name="test_ok" />
    <testcase classname="tests.test_app" name="test_boom" file="tests/test_app.py" line="11">
      <failure message="assert 1 == 2">src/app.py:12: in compute
    assert 1 == 2</failure>
    </testcase>
  </testsuite>
</testsuites>
"""


class TestExtractFailureLocation:
    def test_parses_dotnet_frame(self):
        file_value, line_value = extract_failure_location(_AKKA_STACK)
        assert file_value.endswith("AkkaSerializerGeneratorDiagnosticsSpec.cs")
        assert line_value == 343

    def test_parses_cpython_frame(self):
        file_value, line_value = extract_failure_location(
            'Traceback:\n  File "src/app.py", line 12, in compute'
        )
        assert file_value == "src/app.py"
        assert line_value == 12

    def test_returns_none_without_location(self):
        assert extract_failure_location("assertion failed") == (None, None)


class TestTrxTestFailureParser:
    def test_extracts_only_failed_results(self, tmp_path: Path):
        results_path = tmp_path / "results.trx"
        results_path.write_text(_TRX_DOCUMENT, encoding="utf-8")

        failures = TrxTestFailureParser().parse(
            TestFailureContext(results_path=results_path)
        )

        assert len(failures) == 1
        failure = failures[0]
        assert failure.test_name == "Akka.Serialization.V2.Tests.Spec.Fails"
        assert failure.class_name == "Akka.Serialization.V2.Tests.Spec"
        assert "AKKASG011" in failure.message
        assert failure.file.endswith("AkkaSerializerGeneratorDiagnosticsSpec.cs")
        assert failure.line == 343

    def test_missing_artifact_returns_no_failures(self, tmp_path: Path):
        parser = TrxTestFailureParser()
        assert parser.parse(TestFailureContext(results_path=tmp_path / "x.trx")) == []

    def test_matches_dotnet_project_type_without_artifact(self):
        assert TrxTestFailureParser().matches(TestFailureContext(project_type="dotnet"))


class TestJunitTestFailureParser:
    def test_extracts_failure_with_location(self, tmp_path: Path):
        results_path = tmp_path / "junit.xml"
        results_path.write_text(_JUNIT_DOCUMENT, encoding="utf-8")

        failures = JunitTestFailureParser().parse(
            TestFailureContext(results_path=results_path)
        )

        assert len(failures) == 1
        assert failures[0].test_name == "test_boom"
        assert failures[0].class_name == "tests.test_app"
        assert failures[0].file == "src/app.py"
        assert failures[0].line == 12


class TestTextTestFailureParser:
    def test_parses_pytest_summary(self):
        failures = TextTestFailureParser().parse(
            TestFailureContext(
                output="FAILED tests/test_app.py::test_boom - AssertionError: 1 != 2"
            )
        )
        assert len(failures) == 1
        assert failures[0].test_name == "tests/test_app.py::test_boom"
        assert "AssertionError" in failures[0].message

    def test_falls_back_to_failing_lines(self):
        failures = TextTestFailureParser().parse(
            TestFailureContext(output="some noise\nassert boom did not hold\n")
        )
        assert len(failures) == 1
        assert failures[0].test_name == "unparsed-test-failure"

    def test_empty_output_yields_nothing(self):
        assert TextTestFailureParser().parse(TestFailureContext(output="  ")) == []


class TestTestFailureParserResolver:
    def test_prefers_trx_for_dotnet_artifact(self, tmp_path: Path):
        results_path = tmp_path / "results.trx"
        results_path.write_text(_TRX_DOCUMENT, encoding="utf-8")

        result = TestFailureParserResolver().parse(
            TestFailureContext(results_path=results_path, project_type="dotnet")
        )

        assert result.parser == "trx"
        assert result.available is True
        assert len(result.failures) == 1

    def test_falls_back_to_text_when_artifact_is_unusable(self, tmp_path: Path):
        results_path = tmp_path / "results.trx"
        results_path.write_text("not xml at all", encoding="utf-8")

        result = TestFailureParserResolver().parse(
            TestFailureContext(
                output="FAILED tests/test_app.py::test_boom - boom",
                results_path=results_path,
                project_type="dotnet",
            )
        )

        assert result.parser == "generic"
        assert len(result.failures) == 1

    def test_respects_max_failures(self):
        output = "\n".join(
            f"FAILED tests/test_app.py::test_{index} - boom" for index in range(10)
        )
        result = TestFailureParserResolver().parse(
            TestFailureContext(output=output), max_failures=3
        )
        assert len(result.failures) == 3
