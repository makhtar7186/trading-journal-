import { RValue } from "@/components/shared/r-value";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent, formatRatio } from "@/lib/format";
import type { Group } from "@/types/api";

const UNDEFINED = <span className="text-muted-foreground">Non défini</span>;

/** Résultats par actif / marché / stratégie. Tableau (comparaison exacte) plutôt que graphique. */
export function GroupsTable({
  title,
  firstColumn,
  groups,
  loading,
}: {
  title: string;
  firstColumn: string;
  groups: Group[] | undefined;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !groups ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : !groups || groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun trade clôturé pour ces filtres.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <caption className="sr-only">{title}</caption>
              <thead className="text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 pr-3 font-normal">{firstColumn}</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Trades</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">G / P / BE</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Win rate</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Expectancy</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Profit factor</th>
                  <th scope="col" className="py-2 pl-3 text-right font-normal">Total</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.key ?? "none"} className="border-t border-border">
                    <th scope="row" className="py-2 pr-3 font-medium">{g.label}</th>
                    <td className="tabular px-3 py-2 text-right">{g.trades}</td>
                    <td className="tabular px-3 py-2 text-right">
                      {g.wins} / {g.losses} / {g.break_even}
                    </td>
                    <td className="tabular px-3 py-2 text-right">{g.win_rate === null ? UNDEFINED : formatPercent(g.win_rate)}</td>
                    <td className="px-3 py-2 text-right"><RValue value={g.expectancy_r} /></td>
                    <td className="tabular px-3 py-2 text-right">{g.profit_factor === null ? UNDEFINED : formatRatio(g.profit_factor)}</td>
                    <td className="py-2 pl-3 text-right font-medium"><RValue value={g.total_r} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
