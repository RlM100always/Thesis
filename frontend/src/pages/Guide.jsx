// In-app reference: what every panel does, for a signed-in owner/staff member
// who already knows the software exists but wants a reminder of what's where.
import { PageHeader } from "../ui/kit";
import PanelGuide from "../components/PanelGuide";

export default function GuidePage() {
  return (
    <div className="page stack">
      <PageHeader title="সাহায্য ও গাইড" subtitle="কোন প্যানেলে কী আছে, এক নজরে।" />
      <PanelGuide subtitle="আপনার এখনকার ভূমিকা অনুযায়ী নিচের কিছু প্যানেল হয়তো সাইডবারে দেখতে পাবেন না — অনুমতি অনুযায়ী দেখানো হয়।" />
    </div>
  );
}
