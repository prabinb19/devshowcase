import type { NextAuthOptions } from "next-auth";
import type { JWT } from "next-auth/jwt";
import GitHubProvider from "next-auth/providers/github";

interface ExtendedToken extends JWT {
  githubId?: string;
  githubUsername?: string;
}

export const authOptions: NextAuthOptions = {
  providers: [
    GitHubProvider({
      clientId: process.env.GITHUB_CLIENT_ID ?? "",
      clientSecret: process.env.GITHUB_CLIENT_SECRET ?? "",
    }),
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account && profile) {
        const t = token as ExtendedToken;
        t.githubId = String((profile as Record<string, unknown>).id ?? "");
        t.githubUsername = String(
          (profile as Record<string, unknown>).login ?? ""
        );
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        const t = token as ExtendedToken;
        const u = session.user as Record<string, unknown>;
        u.githubId = t.githubId ?? "";
        u.githubUsername = t.githubUsername ?? "";
      }
      return session;
    },
  },
  pages: {
    signIn: "/",
  },
};
