/** Menu z alergenami (14 alergenów z rozporządzenia UE 1169/2011) i ostrzeżeniami o dietach gości. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useRef, useState } from "react";
import { Button as AriaButton, Form } from "react-aria-components";

import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { userMessage } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Field";
import { ConfirmDialog, Sheet } from "../../components/Overlay";
import { Select } from "../../components/Select";
import { Card, EmptyState, Notice, Skeleton, StatusChip } from "../../components/Surface";
import { useToast } from "../../components/Toast";
import { ALLERGEN_LABELS, COURSE_LABELS, dishTags, type Allergen, type Course } from "../../lib/menu";
import { GUEST_SECTIONS, SectionNav } from "./SectionNav";
import { useCanWrite, useWeddingId } from "./data";
import { ifMatch, saveErrorMessage } from "./mutations";

type Overview = components["schemas"]["MenuOverview"];
type Dish = Overview["dishes"][number];

export function MenuView() {
  const id = useWeddingId();
  const canWrite = useCanWrite(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["wedding", id, "menu"];
  const path = { params: { path: { wedding_id: id } } };
  const data = useQuery({ queryKey: key, queryFn: ({ signal }) => unwrap(api.GET("/api/v1/weddings/{wedding_id}/menu", { ...path, signal })) });
  const [editing, setEditing] = useState<Dish | null>(null);
  const [error, setError] = useState<string | null>(null);
  const show = useMutation({
    mutationFn: (enabled: boolean) => unwrap(api.PUT("/api/v1/weddings/{wedding_id}/menu/show", { ...path, body: { enabled } })),
    onSuccess: async (r) => {
      await queryClient.invalidateQueries({ queryKey: key });
      toast(r.enabled ? "Menu widoczne na stronie gościa" : "Menu ukryte przed gośćmi");
    },
    onError: (e) => setError(userMessage(e)),
  });
  const o = data.data;
  const courses = (Object.keys(COURSE_LABELS) as Course[])
    .map((c) => ({ id: c, dishes: (o?.dishes ?? []).filter((d) => d.course === c) }))
    .filter((c) => c.dishes.length > 0);
  const diets = o ? [o.diets.vegetarian && `wegetariańska: ${o.diets.vegetarian}`, o.diets.vegan && `wegańska: ${o.diets.vegan}`, o.diets.gluten_free && `bezglutenowa: ${o.diets.gluten_free}`].filter(Boolean) : [];

  return (
    <main className="page enter-tab" aria-labelledby="menu-h">
      <SectionNav label="Goście" sections={GUEST_SECTIONS} />
      <div>
        <h1 id="menu-h">Menu</h1>
        <p className="text-secondary">
          Dania z alergenami według informacji od sali. Sprawdzimy, czy goście na diecie mają co zjeść, a menu możecie pokazać gościom
          na ich stronie.
        </p>
      </div>
      {data.isPending && <Skeleton lines={4} />}
      {data.isError && (
        <Notice tone="error" live>
          {userMessage(data.error)}
        </Notice>
      )}
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      {o && (
        <>
          {diets.length > 0 && <p className="text-secondary">Diety na liście gości — {diets.join(", ")}.</p>}
          {o.warnings.map((w) => (
            <Notice key={w} tone="warning">
              {w}
            </Notice>
          ))}
          {canWrite && (
            <Card>
              <Checkbox isSelected={o.show_to_guests} isDisabled={show.isPending} onChange={(v) => show.mutate(v)}>
                Pokaż menu na stronie gościa (z alergenami, bez listy gości)
              </Checkbox>
            </Card>
          )}
          {courses.length === 0 && (
            <EmptyState title="Menu jest puste">
              {canWrite ? "Przepiszcie menu z oferty sali — z alergenami, które sala podała." : "Para nie dodała jeszcze menu."}
            </EmptyState>
          )}
          {courses.map((c) => (
            <section key={c.id} className="form-stack" aria-labelledby={`course-${c.id}`}>
              <h2 id={`course-${c.id}`}>{COURSE_LABELS[c.id]}</h2>
              <Card>
                <ul className="row-list">
                  {c.dishes.map((d) => (
                    <li key={d.id} className="row">
                      <span className="row__body">
                        <span className="row__title">{d.name}</span>
                        {d.description && <span className="text-secondary">{d.description}</span>}
                        <span className="chip-list">
                          {dishTags(d).map((t) => (
                            <StatusChip key={t} tone={t.startsWith("alergeny") ? "warning" : "success"}>
                              {t}
                            </StatusChip>
                          ))}
                        </span>
                      </span>
                      {canWrite && (
                        <AriaButton className="wp-icon-button" aria-label={`Edytuj: ${d.name}`} onPress={() => setEditing(d)}>
                          <Pencil aria-hidden size={20} />
                        </AriaButton>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}
          {canWrite && (
            <Card className="form-stack">
              <h2 className="card-title">Dodaj danie</h2>
              <DishForm weddingId={id} queryKey={key} />
            </Card>
          )}
        </>
      )}
      <Sheet title={editing ? editing.name : "Danie"} isOpen={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        {editing && <DishForm key={editing.id} weddingId={id} queryKey={key} dish={editing} onDone={() => setEditing(null)} />}
      </Sheet>
    </main>
  );
}

function DishForm({ weddingId, queryKey, dish, onDone }: { weddingId: string; queryKey: unknown[]; dish?: Dish; onDone?: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [course, setCourse] = useState<Course>(dish?.course ?? "main");
  const [name, setName] = useState(dish?.name ?? "");
  const [description, setDescription] = useState(dish?.description ?? "");
  const [allergens, setAllergens] = useState<Set<Allergen>>(new Set(dish?.allergens ?? []));
  const [vegetarian, setVegetarian] = useState(dish?.vegetarian ?? false);
  const [vegan, setVegan] = useState(dish?.vegan ?? false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idem = useRef(newIdempotencyKey());
  const body = { course, name: name.trim(), description: description.trim() || null, allergens: [...allergens], vegetarian: vegetarian || vegan, vegan };
  const save = useMutation({
    mutationFn: () =>
      dish
        ? unwrap(
            api.PATCH("/api/v1/weddings/{wedding_id}/menu/{dish_id}", {
              params: { path: { wedding_id: weddingId, dish_id: dish.id } },
              body,
              headers: ifMatch(dish.version),
            }),
          )
        : unwrap(api.POST("/api/v1/weddings/{wedding_id}/menu", { params: { path: { wedding_id: weddingId } }, body, headers: { "Idempotency-Key": idem.current } })),
    onSuccess: (o) => {
      queryClient.setQueryData(queryKey, o);
      if (dish) {
        toast("Zapisano danie");
        onDone?.();
        return;
      }
      idem.current = newIdempotencyKey();
      setName("");
      setDescription("");
      setAllergens(new Set());
      setVegetarian(false);
      setVegan(false);
      setError(null);
      toast("Dodano danie");
    },
    onError: (e) => setError(saveErrorMessage(e, queryClient, [queryKey])),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/weddings/{wedding_id}/menu/{dish_id}", { params: { path: { wedding_id: weddingId, dish_id: dish!.id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey });
      toast("Usunięto danie");
      onDone?.();
    },
    onError: (e) => setError(userMessage(e)),
  });
  return (
    <Form
      className="form-stack"
      aria-label={dish ? "Edycja dania" : "Nowe danie"}
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) save.mutate();
      }}
    >
      <Select label="Danie menu" options={(Object.keys(COURSE_LABELS) as Course[]).map((c) => ({ id: c, label: COURSE_LABELS[c] }))} value={course} onChange={(v) => setCourse(v as Course)} />
      <TextField label="Nazwa" value={name} onChange={setName} maxLength={200} autoComplete="off" isRequired />
      <TextField label="Opis (opcjonalnie)" value={description} onChange={setDescription} maxLength={300} autoComplete="off" />
      <div className="chip-list">
        <Checkbox isSelected={vegetarian || vegan} isDisabled={vegan} onChange={setVegetarian}>
          Wegetariańskie
        </Checkbox>
        <Checkbox isSelected={vegan} onChange={setVegan}>
          Wegańskie
        </Checkbox>
      </div>
      <fieldset className="wp-fieldset allergen-grid">
        <legend className="wp-field__label">Alergeny (według sali)</legend>
        {(Object.keys(ALLERGEN_LABELS) as Allergen[]).map((a) => (
          <Checkbox
            key={a}
            isSelected={allergens.has(a)}
            onChange={(v) =>
              setAllergens((s) => {
                const next = new Set(s);
                if (v) next.add(a);
                else next.delete(a);
                return next;
              })
            }
          >
            {ALLERGEN_LABELS[a]}
          </Checkbox>
        ))}
      </fieldset>
      {error && (
        <Notice tone="error" live>
          {error}
        </Notice>
      )}
      <div className="wp-sheet__actions">
        <Button type="submit" variant={dish ? "primary" : "secondary"} pending={save.isPending} isDisabled={!name.trim()}>
          {dish ? "Zapisz" : "Dodaj danie"}
        </Button>
        {dish && (
          <Button variant="text" onPress={() => setConfirm(true)}>
            Usuń danie
          </Button>
        )}
      </div>
      {dish && (
        <ConfirmDialog title="Usunąć danie?" isOpen={confirm} onOpenChange={setConfirm}>
          <p>Danie „{dish.name}” zniknie z menu.</p>
          <div className="wp-sheet__actions">
            <Button variant="secondary" onPress={() => setConfirm(false)}>
              Zostaw
            </Button>
            <Button variant="danger" pending={remove.isPending} onPress={() => remove.mutate()}>
              Usuń
            </Button>
          </div>
        </ConfirmDialog>
      )}
    </Form>
  );
}
