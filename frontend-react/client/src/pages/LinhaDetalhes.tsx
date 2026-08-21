/**
 * LinhaDetalhes — DEPRECATED (substituída por LineDeepView).
 *
 * Esta era a tela "antiga" de detalhe de linha (1040 linhas com Recharts +
 * shadcn Card/Tabs). O design ficou inconsistente com a POC ISA-101 e a
 * substituição é o `LineDeepView`, mais alinhado com `04_POC_UI.html`.
 *
 * Mantemos esta rota viva para não quebrar bookmarks/links antigos: a
 * página agora simplesmente redireciona para o caminho v2
 * (`/linha/<codigo>/detalhes`).
 *
 * Remoção definitiva: assim que os relatórios e dashboards externos forem
 * atualizados para o novo URL, podemos apagar este arquivo e a rota
 * `/linha/:linhaId` em App.tsx.
 */
import React, { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

const LinhaDetalhes: React.FC = () => {
  const { linhaId } = useParams<{ linhaId: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    if (linhaId) {
      // replace: true → não polui o histórico do navegador com a rota legacy
      navigate(`/linha/${encodeURIComponent(linhaId)}/detalhes`, { replace: true });
    } else {
      navigate("/", { replace: true });
    }
  }, [linhaId, navigate]);

  return (
    <div className="isa-root" style={{ padding: 32, textAlign: "center" }}>
      <p style={{ color: "var(--isa-text-muted)", fontSize: "var(--isa-fs-default)" }}>
        Redirecionando para a visão atualizada da linha…
      </p>
    </div>
  );
};

export default LinhaDetalhes;
