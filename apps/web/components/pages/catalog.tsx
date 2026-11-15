"use client";
import { useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Camera,
  Check,
  Download,
  FileSpreadsheet,
  Package,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { money } from "@/lib/utils";
import { useUI } from "@/store/ui";
import type { Product } from "@/types";
import {
  Badge,
  Busy,
  Empty,
  ErrorState,
  Loading,
  Modal,
  PageTitle,
  Panel,
} from "../shared";
import { Button } from "../ui/button";
import "./utility.css";

type Draft = {
  name: string;
  category: string;
  unit: string;
  selling_price: string;
  available_stock: string;
  purchase_price: string;
  minimum_selling_price: string;
  supplier: string;
};
type Extracted = {
  name: string;
  quantity: number;
  unit: string;
  price: number;
  category?: string;
};
type Extraction = {
  items: Extracted[];
  provider: string;
  demo: boolean;
  error?: string;
  notice?: string;
  review_required: boolean;
};
const blank: Draft = {
  name: "",
  category: "Grocery",
  unit: "kg",
  selling_price: "",
  available_stock: "",
  purchase_price: "",
  minimum_selling_price: "",
  supplier: "",
};

export default function Catalog() {
  const query = useQuery({
    queryKey: ["catalog"],
    queryFn: () => api<Product[]>("/catalog/products"),
  });
  const client = useQueryClient();
  const { notify } = useUI();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All categories");
  const [editing, setEditing] = useState<Product | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(blank);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState<Product | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [lines, setLines] = useState<Extracted[]>([]);
  const csvInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const products = useMemo(() => query.data || [], [query.data]);
  const filtered = useMemo(
    () =>
      products.filter(
        (p) =>
          (category === "All categories" || p.category === category) &&
          `${p.name} ${p.supplier}`
            .toLowerCase()
            .includes(search.toLowerCase()),
      ),
    [products, category, search],
  );
  function openForm(product?: Product) {
    setEditing(product || null);
    setDraft(
      product
        ? {
            name: product.name,
            category: product.category,
            unit: product.unit,
            selling_price: String(product.selling_price),
            available_stock: String(product.available_stock),
            purchase_price: String(product.purchase_price),
            minimum_selling_price: String(product.minimum_selling_price),
            supplier: product.supplier,
          }
        : blank,
    );
    setFormOpen(true);
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const body = {
        ...draft,
        selling_price: Number(draft.selling_price),
        available_stock: Number(draft.available_stock),
        purchase_price: Number(draft.purchase_price),
        minimum_selling_price: Number(draft.minimum_selling_price),
      };
      await api<Product>(
        editing ? `/catalog/products/${editing.id}` : "/catalog/products",
        { method: editing ? "PATCH" : "POST", body: JSON.stringify(body) },
      );
      await client.invalidateQueries({ queryKey: ["catalog"] });
      setFormOpen(false);
      notify(editing ? "Product updated." : "Product added to your catalogue.");
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setSaving(false);
    }
  }
  async function remove() {
    if (!removing) return;
    setSaving(true);
    try {
      await api(`/catalog/products/${removing.id}`, { method: "DELETE" });
      await client.invalidateQueries({ queryKey: ["catalog"] });
      setRemoving(null);
      notify("Product removed.");
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setSaving(false);
    }
  }
  async function importFile(file: File, kind: "csv" | "image") {
    if (file.size > 10 * 1024 * 1024) {
      notify("Choose a file under 10 MB.", "error");
      return;
    }
    setProcessing(true);
    try {
      const body = new FormData();
      body.append("file", file);
      if (kind === "csv") {
        const result = await api<{ imported: number }>("/catalog/import", {
          method: "POST",
          body,
        });
        await client.invalidateQueries({ queryKey: ["catalog"] });
        notify(`${result.imported} products imported from CSV.`);
        setImportOpen(false);
      } else {
        body.append("language", "hi-IN");
        const result = await api<Extraction>("/documents/extract", {
          method: "POST",
          body,
        });
        setExtraction(result);
        setLines(result.items.map((i) => ({ ...i, category: "Grocery" })));
      }
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setProcessing(false);
      if (csvInput.current) csvInput.current.value = "";
      if (imageInput.current) imageInput.current.value = "";
    }
  }
  function downloadSample() {
    const content =
      "name,category,unit,selling_price,available_stock,purchase_price,minimum_selling_price,supplier\nToor Dal,Pulses,kg,145,80,115,125,Pune Grocery Distributors\nPoha,Grocery,kg,65,100,48,55,Sharma Wholesale Mart\n";
    const url = URL.createObjectURL(new Blob([content], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "pehchaan-catalogue-template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  async function saveReviewed() {
    if (!lines.length) return;
    if (
      lines.some(
        (l) =>
          !l.name.trim() || l.price <= 0 || l.quantity < 0 || !l.unit.trim(),
      )
    ) {
      notify(
        "Each reviewed line needs a name, positive price, unit, and nonnegative stock.",
        "error",
      );
      return;
    }
    setSaving(true);
    let saved = 0;
    try {
      for (const line of lines) {
        await api("/catalog/products", {
          method: "POST",
          body: JSON.stringify({
            name: line.name,
            category: line.category || "Grocery",
            unit: line.unit,
            selling_price: line.price,
            available_stock: Math.floor(line.quantity),
            purchase_price: Math.round(line.price * 0.75 * 100) / 100,
            minimum_selling_price: Math.round(line.price * 0.85 * 100) / 100,
            supplier: "Reviewed document import",
          }),
        });
        saved++;
      }
      setLines([]);
      setExtraction(null);
      setImportOpen(false);
      notify(
        `${saved} reviewed products saved. Review merchant costs in Edit product.`,
      );
    } catch (e) {
      setLines((current) => current.slice(saved));
      notify(`${saved} products saved. ${(e as Error).message}`, "error");
    } finally {
      await client.invalidateQueries({ queryKey: ["catalog"] });
      setSaving(false);
    }
  }
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  return (
    <>
      <PageTitle
        eyebrow="WORKSPACE / INVENTORY"
        title="Product catalogue"
        description="Your shelves, prices, and stock. Keep every agent working with the right numbers."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setImportOpen(true);
                setExtraction(null);
                setLines([]);
              }}
            >
              <Upload size={15} />
              Import catalogue
            </Button>
            <Button onClick={() => openForm()}>
              <Plus size={16} />
              Add product
            </Button>
          </>
        }
      />
      <div className="utility-status-row">
        <Badge tone="green">{products.length} PRODUCTS</Badge>
        <Badge>
          {new Set(products.map((p) => p.category)).size} CATEGORIES
        </Badge>
        <span className="utility-body" style={{ margin: 0 }}>
          Merchant view · Cost and minimum prices stay within this workspace
        </span>
      </div>
      <Panel
        title="Merchant inventory"
        subtitle="Synthetic demonstration catalogue · INR"
      >
        <div className="utility-catalog-toolbar">
          <div className="utility-search">
            <Search size={15} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search products or suppliers"
              aria-label="Search products"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label="Filter category"
          >
            <option>All categories</option>
            {[...new Set(products.map((p) => p.category))].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </div>
        {filtered.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Category</th>
                  <th>Selling price</th>
                  <th>Stock</th>
                  <th>Purchase cost</th>
                  <th>Minimum price</th>
                  <th>Supplier</th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.name}</strong>
                      <small>{p.unit}</small>
                    </td>
                    <td>{p.category}</td>
                    <td className="mono">{money(p.selling_price)}</td>
                    <td>
                      <Badge tone={p.available_stock > 20 ? "green" : "amber"}>
                        {p.available_stock} {p.unit}
                      </Badge>
                    </td>
                    <td className="mono">{money(p.purchase_price)}</td>
                    <td className="mono">{money(p.minimum_selling_price)}</td>
                    <td>{p.supplier}</td>
                    <td>
                      <div className="utility-table-actions">
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Edit ${p.name}`}
                          onClick={() => openForm(p)}
                        >
                          <Pencil size={14} />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Delete ${p.name}`}
                          onClick={() => setRemoving(p)}
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="No matching products"
            description="Adjust the search, or add your first product to the catalogue."
          />
        )}
        <div className="utility-pagination">
          <span>
            Showing {filtered.length} of {products.length} products
          </span>
          <span>
            <Package
              size={13}
              style={{
                display: "inline",
                verticalAlign: "middle",
                marginRight: 6,
              }}
            />
            Inventory updates are saved to the database
          </span>
        </div>
      </Panel>
      <Modal
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editing ? "Edit product" : "Add a product"}
        description="Set the merchant-owned stock and pricing rules. Values are validated before saving."
      >
        <form onSubmit={save}>
          <div className="form-grid">
            {(
              [
                ["name", "Product name", "text"],
                ["category", "Category", "text"],
                ["unit", "Unit", "text"],
                ["supplier", "Supplier", "text"],
                ["selling_price", "Selling price (₹)", "number"],
                ["available_stock", "Available stock", "number"],
                ["purchase_price", "Purchase cost (₹)", "number"],
                [
                  "minimum_selling_price",
                  "Minimum selling price (₹)",
                  "number",
                ],
              ] as const
            ).map(([key, label, type]) => (
              <label className="field" key={key}>
                <span>{label}</span>
                <input
                  value={draft[key]}
                  type={type}
                  required
                  min={
                    key === "available_stock" || key === "purchase_price"
                      ? 0
                      : 0.01
                  }
                  step={key === "available_stock" ? 1 : 0.01}
                  onChange={(e) =>
                    setDraft({ ...draft, [key]: e.target.value })
                  }
                />
              </label>
            ))}
          </div>
          <div className="utility-form-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setFormOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <Busy>Saving…</Busy>
              ) : (
                <>
                  <Check size={15} />
                  {editing ? "Save changes" : "Add product"}
                </>
              )}
            </Button>
          </div>
        </form>
      </Modal>
      <Modal
        open={!!removing}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
        title="Remove this product?"
        description={`${removing?.name || "This product"} will be removed from the merchant catalogue.`}
      >
        <div className="utility-form-actions">
          <Button variant="secondary" onClick={() => setRemoving(null)}>
            Keep product
          </Button>
          <Button variant="destructive" disabled={saving} onClick={remove}>
            {saving ? "Removing…" : "Delete product"}
          </Button>
        </div>
      </Modal>
      <Modal
        open={importOpen}
        onOpenChange={setImportOpen}
        title="Import your catalogue"
        description="Upload a CSV, or review assisted extraction from a photographed rate card."
      >
        <input
          ref={csvInput}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          aria-label="Upload catalogue CSV"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void importFile(f, "csv");
          }}
        />
        <input
          ref={imageInput}
          type="file"
          accept="image/png,image/jpeg,image/webp,application/pdf"
          className="sr-only"
          aria-label="Upload rate card document"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void importFile(f, "image");
          }}
        />
        {!extraction ? (
          <>
            <div
              className="utility-catalog-actions"
              style={{ marginBottom: 18 }}
            >
              <Button
                variant="secondary"
                disabled={processing}
                onClick={() => csvInput.current?.click()}
              >
                <FileSpreadsheet size={16} />
                Upload CSV
              </Button>
              <Button
                variant="secondary"
                disabled={processing}
                onClick={() => imageInput.current?.click()}
              >
                <Camera size={16} />
                Photograph / document
              </Button>
              <Button
                variant="ghost"
                disabled={processing}
                onClick={downloadSample}
              >
                <Download size={15} />
                CSV template
              </Button>
            </div>
            <div className="utility-note">
              <ShieldCheck size={17} />
              <span>
                CSV imports validate every row. Document extraction always
                requires review before saving. Files must be under 10 MB.
              </span>
            </div>
            {processing && (
              <div style={{ padding: "22px 0" }}>
                <Busy>Processing your file…</Busy>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="utility-note" style={{ marginBottom: 16 }}>
              <AlertCircle size={17} />
              <span>
                <strong>
                  {extraction.demo
                    ? "DEMO SAMPLE · Not extracted from your file"
                    : "SARVAM EXTRACTION · Review required"}
                </strong>
                <br />
                {extraction.notice ||
                  extraction.error ||
                  "Correct each product, quantity, and price before saving."}
                <br />
                Purchase cost defaults to 75% and minimum price to 85% of
                reviewed selling price. Edit the saved products to set your own
                mandates.
              </span>
            </div>
            <div className="table-wrap">
              <table className="data-table utility-preview-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Stock</th>
                    <th>Unit</th>
                    <th>Price ₹</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line, i) => (
                    <tr key={i}>
                      <td>
                        <input
                          aria-label={`Product name ${i + 1}`}
                          value={line.name}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, n) =>
                                n === i ? { ...l, name: e.target.value } : l,
                              ),
                            )
                          }
                        />
                      </td>
                      <td>
                        <input
                          className="number-input"
                          type="number"
                          min={0}
                          aria-label={`Stock ${i + 1}`}
                          value={line.quantity}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, n) =>
                                n === i
                                  ? { ...l, quantity: Number(e.target.value) }
                                  : l,
                              ),
                            )
                          }
                        />
                      </td>
                      <td>
                        <input
                          className="number-input"
                          aria-label={`Unit ${i + 1}`}
                          value={line.unit}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, n) =>
                                n === i ? { ...l, unit: e.target.value } : l,
                              ),
                            )
                          }
                        />
                      </td>
                      <td>
                        <input
                          className="number-input"
                          type="number"
                          min={0.01}
                          step={0.01}
                          aria-label={`Price ${i + 1}`}
                          value={line.price}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, n) =>
                                n === i
                                  ? { ...l, price: Number(e.target.value) }
                                  : l,
                              ),
                            )
                          }
                        />
                      </td>
                      <td>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove extracted row ${i + 1}`}
                          onClick={() =>
                            setLines(lines.filter((_, n) => n !== i))
                          }
                        >
                          <X size={13} />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="utility-form-actions">
              <Button
                variant="secondary"
                disabled={saving}
                onClick={() => {
                  setExtraction(null);
                  setLines([]);
                }}
              >
                Choose another file
              </Button>
              <Button disabled={saving || !lines.length} onClick={saveReviewed}>
                {saving ? (
                  <Busy>Saving reviewed products…</Busy>
                ) : (
                  <>
                    <Check size={15} />
                    Approve & save {lines.length} products
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </Modal>
    </>
  );
}
