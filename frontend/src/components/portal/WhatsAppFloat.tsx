import { Link } from "@chakra-ui/react";
import { PORTAL_CONTACT } from "./PortalFooter";

export function WhatsAppFloat() {
  return (
    <Link
      href={PORTAL_CONTACT.whatsappUrl}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Contactar por WhatsApp"
      position="fixed"
      bottom={6}
      right={6}
      zIndex={40}
      touchAction="manipulation"
      boxSize={14}
      borderRadius="full"
      bg="#25D366"
      color="white"
      display="flex"
      alignItems="center"
      justifyContent="center"
      boxShadow="lg"
      _hover={{ transform: "scale(1.06)" }}
      _active={{ transform: "scale(0.97)" }}
      transition="transform 150ms ease-out"
      _motionReduce={{ transition: "none", _hover: { transform: "none" } }}
    >
      <svg className="icon-inline" width={28} height={28} aria-hidden="true">
        <use xlinkHref="#whatsapp" />
      </svg>
    </Link>
  );
}
