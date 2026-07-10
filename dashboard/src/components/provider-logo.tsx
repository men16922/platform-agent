/* eslint-disable @next/next/no-img-element -- provider logos are external SVG marks with fixed display dimensions. */
type Provider = "aws" | "gcp" | "azure" | "onprem";

const providerLogos: Record<Provider, { src: string; alt: string }> = {
  aws: { src: "/providers/aws-mark.svg", alt: "AWS" },
  gcp: { src: "/providers/gcp.svg", alt: "Google Cloud" },
  azure: { src: "/providers/azure.svg", alt: "Microsoft Azure" },
  onprem: { src: "/providers/cncf-mark.svg", alt: "Cloud Native Computing Foundation" },
};

export function ProviderLogo({ provider, size = "md" }: { provider: Provider; size?: "sm" | "md" }) {
  const logo = providerLogos[provider];
  const dimensions = size === "sm"
    ? provider === "aws" || provider === "onprem" ? "h-3.5 w-6" : "h-4 w-4"
    : provider === "aws" ? "h-6 w-10" : provider === "onprem" ? "h-7 w-7" : "h-6 w-6";
  return <img src={logo.src} alt={logo.alt} className={`${dimensions} object-contain`} />;
}

export const providerBadgeStyles: Record<Provider, string> = {
  aws: "border-[#ff9900]/60 bg-[#ff9900]/25 text-[#ffd199]",
  gcp: "border-[#8ab4f8]/65 bg-[#4285f4]/30 text-[#dceaff]",
  azure: "border-[#00a4ef]/65 bg-[#0078d4]/35 text-[#b8ecff]",
  onprem: "border-[#69d3a7]/60 bg-[#16845a]/30 text-[#c7f6dc]",
};
