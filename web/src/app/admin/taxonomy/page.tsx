import type { Route } from "next";
import { redirect } from "next/navigation";

export default function Page() {
  redirect("/admin/taxonomy/template-draft" as Route);
}
