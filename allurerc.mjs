// Allure 3 report configuration (used by: npx allure generate / npx allure open)
// Docs: https://allurereport.org/docs/v3/configure/
export default {
  name: "Desktop & CLI Automation - Test Report",
  output: "./allure-report",
  // Keeps previous runs so the report can show history and trends.
  historyPath: "./allure-history/history.jsonl",
  plugins: {
    awesome: {
      options: {
        // One self-contained index.html: easy to email or upload as a CI artifact.
        singleFile: true,
        reportLanguage: "en",
        groupBy: ["epic", "feature", "story"],
      },
    },
  },
};
