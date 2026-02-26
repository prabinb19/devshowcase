export { default } from "next-auth/middleware";

export const config = {
  matcher: ["/dashboard/:path*", "/runs/:path*", "/drafts/:path*", "/history/:path*"],
};
