"use client";

/* eslint-disable @next/next/no-img-element -- model marks are small local brand assets with a text fallback. */

// Interactive image split into a client component: the onError monogram
// fallback needs an event handler, which server components can't pass as a prop.
export function ModelLogoImg({ src, alt, label }: { src: string; alt: string; label: string }) {
  return (
    <img
      src={src}
      alt={alt}
      className="h-full w-full rounded-[3px] object-contain p-px"
      onError={(event) => {
        event.currentTarget.style.display = "none";
        event.currentTarget.parentElement?.append(label);
      }}
    />
  );
}
