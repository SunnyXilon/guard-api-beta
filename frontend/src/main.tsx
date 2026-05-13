import React from "react";
import ReactDOM from "react-dom/client";
import { ClerkProvider, useAuth } from "@clerk/react";
import { App } from "./App";
import "./styles.css";

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

function ClerkAuthedApp() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return <App clerkEnabled clerkLoaded={Boolean(isLoaded)} clerkSignedIn={Boolean(isSignedIn)} getClerkToken={getToken} />;
}

const root = (
  <React.StrictMode>
    {clerkPublishableKey ? (
      <ClerkProvider
        publishableKey={clerkPublishableKey}
        signInForceRedirectUrl="/dashboard"
        signUpForceRedirectUrl="/dashboard"
        signInFallbackRedirectUrl="/dashboard"
        signUpFallbackRedirectUrl="/dashboard"
      >
        <ClerkAuthedApp />
      </ClerkProvider>
    ) : (
      <App clerkEnabled={false} clerkLoaded clerkSignedIn={false} getClerkToken={async () => null} />
    )}
  </React.StrictMode>
);

ReactDOM.createRoot(document.getElementById("root")!).render(root);
