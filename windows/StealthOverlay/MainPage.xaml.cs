using Microsoft.UI.Xaml;
using Microsoft.UI.Windowing;
using WinRT.Interop;
using System;

namespace StealthOverlay
{
    public sealed partial class MainPage : Microsoft.UI.Xaml.Controls.Page
    {
        public MainPage()
        {
            this.InitializeComponent();
            
            // Set up configurations once the window is initialized
            this.Loaded += MainPage_Loaded;
        }

        private void MainPage_Loaded(object sender, RoutedEventArgs e)
        {
            IntPtr windowHandle = WindowNative.GetWindowHandle(App.CurrentWindow);
            Microsoft.UI.WindowId windowId = Microsoft.UI.Win32Interop.GetWindowIdFromWindowHandle(windowHandle);
            AppWindow appWindow = AppWindow.GetFromWindowId(windowId);

            if (appWindow != null)
            {
                // Set the title matching the Python monitoring thread
                appWindow.Title = "StealthOverlay";

                OverlappedPresenter presenter = appWindow.Presenter as OverlappedPresenter;
                if (presenter != null)
                {
                    presenter.IsAlwaysOnTop = true;       // Floats above other apps
                    presenter.IsResizable = false;         // Lock dimensions
                    presenter.HasTitleBar = false;         // Borderless, no window chrome
                }
            }
        }
    }
}