   declare global {
     interface Window {
       OneSignal: any;
       OneSignalDeferred: any[];
     }

     const OneSignal: any;
     const OneSignalDeferred: any[];
   }

   export {};