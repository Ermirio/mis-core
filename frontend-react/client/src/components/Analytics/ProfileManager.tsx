import React, { useState, useEffect } from 'react';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Save, FolderOpen, Trash2, Copy, Star } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import axios from 'axios';
import { DJANGO_API_URL as DJANGO_API } from "@/config/api";

interface Profile {
    id: number;
    nome: string;
    descricao: string;
    config: any;
    criado_em: string;
    atualizado_em: string;
}

interface ProfileManagerProps {
    linhaId: number | null;
    currentState: any;
    onLoadProfile: (config: any) => void;
}

export const ProfileManager: React.FC<ProfileManagerProps> = ({
    linhaId, currentState, onLoadProfile
}) => {
    const [profiles, setProfiles] = useState<Profile[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [newProfileName, setNewProfileName] = useState('');
    const [newProfileDesc, setNewProfileDesc] = useState('');



    useEffect(() => {
        if (isOpen && linhaId) loadProfiles();
    }, [isOpen, linhaId]);

    const loadProfiles = async () => {
        if (!linhaId) return;
        try {
            const res = await axios.get(`${DJANGO_API}/analytics-profiles/?linha=${linhaId}`);
            setProfiles(res.data.results || res.data);
        } catch (err) {
            console.error('Erro ao carregar perfis:', err);
        }
    };

    const saveProfile = async () => {
        if (!newProfileName.trim()) {
            alert('Nome do perfil é obrigatório');
            return;
        }

        if (!linhaId) {
            alert('Linha não identificada');
            return;
        }

        setIsSaving(true);
        try {
            await axios.post(`${DJANGO_API}/analytics-profiles/`, {
                nome: newProfileName,
                descricao: newProfileDesc,
                linha: linhaId,
                config: currentState
            });

            setNewProfileName('');
            setNewProfileDesc('');
            loadProfiles();
            alert('Perfil salvo com sucesso!');
        } catch (err: any) {
            const errorMsg = err.response?.data?.nome?.[0] || err.response?.data?.detail || err.message;
            alert(`Erro: ${errorMsg}`);
        } finally {
            setIsSaving(false);
        }
    };

    const deleteProfile = async (id: number) => {
        if (!confirm('Deseja realmente excluir este perfil?')) return;

        try {
            await axios.delete(`${DJANGO_API}/analytics-profiles/${id}/`);
            loadProfiles();
        } catch (err) {
            alert('Erro ao excluir perfil');
        }
    };

    const duplicateProfile = async (id: number) => {
        try {
            await axios.post(`${DJANGO_API}/analytics-profiles/${id}/duplicate/`, {
                nome: `${profiles.find(p => p.id === id)?.nome} (Cópia)`
            });
            loadProfiles();
        } catch (err) {
            alert('Erro ao duplicar perfil');
        }
    };

    const applyProfile = (config: any) => {
        onLoadProfile(config);
        setIsOpen(false);
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                    <FolderOpen className="h-4 w-4" />
                    Perfis
                </Button>
            </DialogTrigger>

            <DialogContent className="max-w-2xl max-h-[80vh]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Star className="h-5 w-5 text-yellow-500" />
                        Perfis de Visualização
                    </DialogTitle>
                    <DialogDescription>
                        Salve configurações de análises para reutilizar posteriormente
                    </DialogDescription>
                </DialogHeader>

                {/* Lista de Perfis Salvos */}
                <div className="border-b pb-4">
                    <h3 className="font-semibold text-sm mb-2">Perfis Salvos</h3>
                    <ScrollArea className="h-48 border rounded-md p-2">
                        {profiles.length === 0 ? (
                            <div className="text-center text-gray-400 py-8">
                                Nenhum perfil salvo ainda
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {profiles.map(profile => (
                                    <div key={profile.id} className="flex items-start gap-2 p-3 rounded-lg border hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                                        <div className="flex-1">
                                            <div className="font-semibold text-sm">{profile.nome}</div>
                                            {profile.descricao && (
                                                <div className="text-xs text-gray-500 mt-1">{profile.descricao}</div>
                                            )}
                                            <div className="flex gap-2 mt-1">
                                                <Badge variant="outline" className="text-[10px]">
                                                    {profile.config.selectedTags?.length || 0} variáveis
                                                </Badge>
                                                <Badge variant="outline" className="text-[10px]">
                                                    {profile.config.hoursBack}h
                                                </Badge>
                                            </div>
                                        </div>
                                        <div className="flex gap-1">
                                            <Button
                                                size="sm"
                                                variant="default"
                                                onClick={() => applyProfile(profile.config)}
                                                className="h-8 px-2 text-xs"
                                            >
                                                Carregar
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => duplicateProfile(profile.id)}
                                                className="h-8 w-8 p-0"
                                                title="Duplicar"
                                            >
                                                <Copy className="h-3 w-3" />
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => deleteProfile(profile.id)}
                                                className="h-8 w-8 p-0 text-red-500 hover:text-red-700"
                                                title="Excluir"
                                            >
                                                <Trash2 className="h-3 w-3" />
                                            </Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </ScrollArea>
                </div>

                {/* Salvar Novo Perfil */}
                <div>
                    <h3 className="font-semibold text-sm mb-3">Salvar Configuração Atual</h3>
                    <Alert className="mb-3">
                        <AlertDescription className="text-xs">
                            {currentState.selectedTags?.length || 0} variáveis selecionadas •
                            Período: {currentState.hoursBack}h •
                            Aba: {currentState.activeTab}
                        </AlertDescription>
                    </Alert>

                    <div className="space-y-3">
                        <div>
                            <Label htmlFor="profile-name">Nome do Perfil *</Label>
                            <Input
                                id="profile-name"
                                placeholder="Ex: Análise Velocidade OEE"
                                value={newProfileName}
                                onChange={e => setNewProfileName(e.target.value)}
                            />
                        </div>
                        <div>
                            <Label htmlFor="profile-desc">Descrição (Opcional)</Label>
                            <Textarea
                                id="profile-desc"
                                placeholder="Descreva o objetivo desta análise..."
                                value={newProfileDesc}
                                onChange={e => setNewProfileDesc(e.target.value)}
                                rows={2}
                            />
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => setIsOpen(false)}>
                        Cancelar
                    </Button>
                    <Button onClick={saveProfile} disabled={isSaving} className="gap-2">
                        <Save className="h-4 w-4" />
                        {isSaving ? 'Salvando...' : 'Salvar Perfil'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
