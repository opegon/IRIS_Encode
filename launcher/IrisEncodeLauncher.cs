// IrisEncodeLauncher.cs — cible du raccourci Bureau d'IRIS ENCODE.
//
// Rôle unique : ouvrir launch.bat dans Windows Terminal (wt.exe), le seul
// hôte où le rendu TUI est optimal — un raccourci direct vers launch.bat
// s'ouvrirait dans la console héritée (conhost), au rendu dégradé.
// À défaut de Windows Terminal, bascule sur une console cmd classique.
//
// Compilé sur place par launcher\build.bat avec le csc.exe du
// .NET Framework 4.x livré avec Windows : aucun binaire tiers, le source
// fait foi. Cible /target:winexe — aucune fenêtre propre, l'exécutable ne
// fait qu'en ouvrir une autre.

using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class IrisEncodeLauncher
{
    [STAThread]
    static void Main()
    {
        // Le dossier de l'exécutable, pas le répertoire courant : lancé par
        // raccourci, le répertoire courant est celui du raccourci.
        string dossier = Path.GetDirectoryName(Application.ExecutablePath);

        if (!File.Exists(Path.Combine(dossier, "launch.bat")))
        {
            MessageBox.Show(
                "launch.bat est introuvable à côté de l'exécutable :\n\n"
                    + dossier
                    + "\n\nIRIS_Encode.exe doit rester dans le dossier "
                    + "d'IRIS ENCODE ; sur le Bureau, ne placer qu'un "
                    + "raccourci vers lui.",
                "IRIS ENCODE",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            Environment.Exit(1);
        }

        // Un « \ » final serait lu « \" » — guillemet échappé — par wt.exe :
        // cas d'un dossier à la racine d'un disque (« D:\ »). Le doubler le
        // rend inerte.
        string entreGuillemets =
            "\"" + (dossier.EndsWith("\\") ? dossier + "\\" : dossier) + "\"";

        // wt.exe est un alias d'exécution (fichier de 0 octet sous
        // WindowsApps) : CreateProcess ne sait pas le résoudre, seul
        // ShellExecute y parvient — d'où UseShellExecute = true.
        try
        {
            Process.Start(new ProcessStartInfo("wt.exe")
            {
                Arguments = "-d " + entreGuillemets + " cmd /c launch.bat",
                UseShellExecute = true,
            });
            return;
        }
        catch (Exception)
        {
            // Windows Terminal absent : launch.bat avertit lui-même du
            // rendu dégradé hors wt (test sur WT_SESSION).
        }

        Process.Start(new ProcessStartInfo("cmd.exe")
        {
            Arguments = "/c launch.bat",
            WorkingDirectory = dossier,
            UseShellExecute = true,
        });
    }
}
