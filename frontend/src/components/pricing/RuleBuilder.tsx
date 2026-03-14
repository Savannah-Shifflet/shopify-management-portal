"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { pricingApi, suppliersApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2, Save, Loader2, X } from "lucide-react";

const CONDITION_TYPES = [
  { value: "always", label: "Always" },
  { value: "cost_range", label: "Cost Range" },
  { value: "product_type", label: "Product Type" },
  { value: "tag", label: "Tag" },
];

interface RuleForm {
  rule_name: string;
  priority: number;
  condition_type: string;
  condition_value: Record<string, string>;
  markup_type: string;
  markup_value: string;
  round_to: string;
}

function emptyRule(): RuleForm {
  return {
    rule_name: "",
    priority: 0,
    condition_type: "always",
    condition_value: {},
    markup_type: "percent",
    markup_value: "",
    round_to: "",
  };
}

function buildConditionValue(form: RuleForm): Record<string, unknown> {
  if (form.condition_type === "cost_range") {
    return {
      min: Number(form.condition_value.min ?? 0),
      max: Number(form.condition_value.max ?? 999999),
    };
  }
  if (form.condition_type === "product_type") return { type: form.condition_value.type ?? "" };
  if (form.condition_type === "tag") return { tag: form.condition_value.tag ?? "" };
  return {};
}

export function RuleBuilder() {
  const qc = useQueryClient();
  const [supplierId, setSupplierId] = useState("");
  const [adding, setAdding] = useState(false);
  const [newRule, setNewRule] = useState<RuleForm>(emptyRule());

  const { data: suppliers } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => suppliersApi.list().then((r) => r.data),
  });

  const { data: rules, isLoading } = useQuery({
    queryKey: ["pricing-rules", supplierId],
    queryFn: () => pricingApi.rules(supplierId).then((r) => r.data),
    enabled: !!supplierId,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      pricingApi.createRule({
        supplier_id: supplierId,
        rule_name: newRule.rule_name || null,
        priority: Number(newRule.priority),
        condition_type: newRule.condition_type,
        condition_value: buildConditionValue(newRule),
        markup_type: newRule.markup_type,
        markup_value: newRule.markup_value || "0",
        round_to: newRule.round_to || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pricing-rules", supplierId] });
      setAdding(false);
      setNewRule(emptyRule());
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => pricingApi.deleteRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pricing-rules", supplierId] }),
  });

  const setField = (field: keyof RuleForm, value: unknown) =>
    setNewRule((r) => ({ ...r, [field]: value }));

  const setConditionField = (key: string, value: string) =>
    setNewRule((r) => ({ ...r, condition_value: { ...r.condition_value, [key]: value } }));

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Pricing Rules</CardTitle>
          {supplierId && (
            <Button size="sm" onClick={() => setAdding(true)} disabled={adding}>
              <Plus className="h-3.5 w-3.5 mr-1" /> Add Rule
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Supplier selector */}
        <div>
          <label className="text-xs font-medium text-gray-500 mb-1 block">Supplier</label>
          <select
            value={supplierId}
            onChange={(e) => { setSupplierId(e.target.value); setAdding(false); setNewRule(emptyRule()); }}
            className="w-full border rounded px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">— Select a supplier —</option>
            {(suppliers || []).map((s: any) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {!supplierId && (
          <p className="text-sm text-gray-400 text-center py-4">
            Select a supplier to manage its pricing rules
          </p>
        )}

        {supplierId && isLoading && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        )}

        {supplierId && !isLoading && (
          <div className="border rounded-lg overflow-hidden text-sm">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b">
                  <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">Name</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">Pri.</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">Condition</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">Markup</th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">Round To</th>
                  <th className="w-10"></th>
                </tr>
              </thead>
              <tbody>
                {(!rules || rules.length === 0) && !adding && (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-gray-400">
                      No rules yet — click "Add Rule" to create one
                    </td>
                  </tr>
                )}

                {(rules || []).map((rule: any) => (
                  <tr key={rule.id} className="border-b last:border-0">
                    <td className="px-3 py-2.5 font-medium">
                      {rule.rule_name || <span className="text-gray-400 italic text-xs">Unnamed</span>}
                    </td>
                    <td className="px-3 py-2.5 text-gray-600">{rule.priority}</td>
                    <td className="px-3 py-2.5 text-xs">
                      <span className="capitalize">{rule.condition_type.replace(/_/g, " ")}</span>
                      {rule.condition_type === "cost_range" && rule.condition_value && (
                        <span className="text-gray-400 ml-1">
                          (${rule.condition_value.min}–${rule.condition_value.max})
                        </span>
                      )}
                      {rule.condition_type === "product_type" && (
                        <span className="text-gray-400 ml-1">= {rule.condition_value?.type}</span>
                      )}
                      {rule.condition_type === "tag" && (
                        <span className="text-gray-400 ml-1">= {rule.condition_value?.tag}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 font-medium">
                      {rule.markup_value}{rule.markup_type === "percent" ? "%" : " fixed ($)"}
                    </td>
                    <td className="px-3 py-2.5 text-gray-500">{rule.round_to ?? "—"}</td>
                    <td className="px-3 py-2.5">
                      <Button
                        variant="ghost" size="icon"
                        className="h-7 w-7 text-gray-400 hover:text-red-500"
                        onClick={() => deleteMutation.mutate(rule.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}

                {/* Inline new-rule form */}
                {adding && (
                  <tr className="border-t bg-blue-50/60">
                    <td className="px-2 py-2">
                      <Input
                        className="h-8 text-xs"
                        placeholder="Rule name"
                        value={newRule.rule_name}
                        onChange={(e) => setField("rule_name", e.target.value)}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Input
                        className="h-8 text-xs w-14"
                        type="number"
                        value={newRule.priority}
                        onChange={(e) => setField("priority", Number(e.target.value))}
                      />
                    </td>
                    <td className="px-2 py-2 space-y-1">
                      <select
                        value={newRule.condition_type}
                        onChange={(e) => {
                          setField("condition_type", e.target.value);
                          setField("condition_value", {});
                        }}
                        className="w-full h-8 text-xs border rounded px-1.5 bg-white"
                      >
                        {CONDITION_TYPES.map((c) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                      {newRule.condition_type === "cost_range" && (
                        <div className="flex gap-1">
                          <Input className="h-7 text-xs" type="number" placeholder="Min $"
                            onChange={(e) => setConditionField("min", e.target.value)} />
                          <Input className="h-7 text-xs" type="number" placeholder="Max $"
                            onChange={(e) => setConditionField("max", e.target.value)} />
                        </div>
                      )}
                      {newRule.condition_type === "product_type" && (
                        <Input className="h-7 text-xs" placeholder="Type name"
                          onChange={(e) => setConditionField("type", e.target.value)} />
                      )}
                      {newRule.condition_type === "tag" && (
                        <Input className="h-7 text-xs" placeholder="Tag value"
                          onChange={(e) => setConditionField("tag", e.target.value)} />
                      )}
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex gap-1 items-center">
                        <Input
                          className="h-8 text-xs w-20"
                          type="number" step="0.01" placeholder="Value"
                          value={newRule.markup_value}
                          onChange={(e) => setField("markup_value", e.target.value)}
                        />
                        <select
                          value={newRule.markup_type}
                          onChange={(e) => setField("markup_type", e.target.value)}
                          className="h-8 text-xs border rounded px-1 bg-white"
                        >
                          <option value="percent">%</option>
                          <option value="fixed">$</option>
                        </select>
                      </div>
                    </td>
                    <td className="px-2 py-2">
                      <Input
                        className="h-8 text-xs w-20"
                        type="number" step="0.01" placeholder="0.99"
                        value={newRule.round_to}
                        onChange={(e) => setField("round_to", e.target.value)}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex gap-1">
                        <Button
                          size="icon" className="h-8 w-8"
                          onClick={() => createMutation.mutate()}
                          disabled={createMutation.isPending}
                        >
                          {createMutation.isPending
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : <Save className="h-3.5 w-3.5" />}
                        </Button>
                        <Button
                          size="icon" variant="outline" className="h-8 w-8"
                          onClick={() => { setAdding(false); setNewRule(emptyRule()); }}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Priority explanation */}
        {supplierId && rules && rules.length > 0 && (
          <p className="text-xs text-gray-400">
            Rules are evaluated highest priority first. First matching rule wins.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
