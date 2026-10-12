import { FaArrowUpRightFromSquare } from "react-icons/fa6";
import i18n from "../../lib/i18n";
import { Button } from "../ui/button";

export function RecoveryCodes({
  recovery,
  complete,
}: {
  recovery: string[];
  complete: () => void;
}) {
  return (
    <div>
      <p>
        {i18n.t(
          "Estos códigos se muestran una sola vez. Guárdalos en tu gestor de contraseñas; cada uno permite un acceso si pierdes tu autenticador.",
        )}
      </p>
      <pre className="recovery">{recovery.join("\n")}</pre>
      <Button onClick={complete}>
        {i18n.t("Ya los guardé. Abrir panel")}
        <FaArrowUpRightFromSquare size={14} />
      </Button>
    </div>
  );
}
