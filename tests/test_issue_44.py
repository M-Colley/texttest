import os
import tempfile
import time
import unittest

from texttestlib.default.batch import summarypages


class TestIssue44(unittest.TestCase):
    def _write_dated_report(self, app_dir, app_title, version, date_str, tag, succeeded=5):
        os.makedirs(app_dir, exist_ok=True)
        overview = os.path.join(app_dir, f"test_{version}.html")
        if not os.path.isfile(overview):
            with open(overview, "w", encoding="utf-8") as f:
                f.write(f"<html><head><title>Test results for {app_title} - version {version}</title></head></html>\n")
        dated = os.path.join(app_dir, f"test_{version}_{date_str}_{tag}.html")
        with open(dated, "w", encoding="utf-8") as f:
            f.write(
                f"<html><head><title>Test results for {app_title} - version {version}</title></head>\n"
                f"<body><H2>Version: {succeeded} tests: {succeeded} succeeded</H2></body></html>\n"
            )

    def _write_jenkins_run_file(self, run_dir, date_str, tag, job_name, build_num):
        os.makedirs(run_dir, exist_ok=True)
        path = os.path.join(run_dir, f"{date_str}_{tag}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f"JENKINS_URL=http://jenkins.example.local/\n"
                f"JOB_NAME={job_name}\n"
                f"BUILD_NUMBER={build_num}\n"
            )

    def test_stale_jenkins_job_excluded_from_recent_and_marked_old_with_dates_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = os.path.join(tmp, "report")
            run_dir = os.path.join(tmp, "repo", "run_names")

            # Suite A ran recently on 26Jan2006 (build 42); Suite B last ran 16 days earlier on 10Jan2006 (build 9)
            self._write_dated_report(os.path.join(report_dir, "app_a"), "Suite A", "default", "26Jan2006", "42", 4)
            self._write_jenkins_run_file(run_dir, "26Jan2006", "42", "SuiteA-Job", "42")

            self._write_dated_report(os.path.join(report_dir, "app_b"), "Suite B", "default", "10Jan2006", "9", 3)
            self._write_jenkins_run_file(run_dir, "10Jan2006", "9", "SuiteB-Job", "9")

            finder = summarypages.SummaryDataFinder(report_dir, [], "index.html", "", False)
            finder.appRuns = {"Suite A": run_dir, "Suite B": run_dir}
            apps_with_versions = finder.getAppsWithVersions()
            self.assertEqual(set(apps_with_versions.keys()), {"Suite A", "Suite B"})

            most_recent = finder.getMostRecentDateAndTags()
            self.assertEqual(len(most_recent), 1)
            self.assertEqual(time.strftime("%d%b%Y", most_recent[0][0]), "26Jan2006")
            self.assertEqual(most_recent[0][1], "42")

            gen = summarypages.SummaryGenerator()
            # Header includes date alongside numeric Jenkins build number instead of bare "42"
            self.assertEqual(gen.getRecentTagText(most_recent), "test run 26Jan2006.42")

            _, last_a, _, _ = finder.getLatestSummaries("Suite A", "default")
            _, last_b, _, _ = finder.getLatestSummaries("Suite B", "default")
            self.assertFalse(gen.showResultAsOld(last_a, most_recent))
            self.assertTrue(gen.showResultAsOld(last_b, most_recent))


if __name__ == "__main__":
    unittest.main()
