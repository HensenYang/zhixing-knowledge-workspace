"""Fetch text-only, pinned official research sources; never model weights."""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'sources'
def fetch(url):
    request = urllib.request.Request(url,headers={'User-Agent':'Unitree-research-workspace'})
    return urllib.request.urlopen(request,timeout=40).read()

SELECTED = {
 'unifolm-world-model-action': [
 'configs/inference/base_model_inference.yaml','configs/inference/world_model_interaction.yaml','configs/inference/world_model_decision_making.yaml',
 'configs/train/config.yaml','scripts/run_base_model_inference.sh','scripts/run_world_model_interaction.sh','scripts/run_real_eval_server.sh',
 'scripts/evaluation/base_model_inference.py','scripts/evaluation/world_model_interaction.py','scripts/evaluation/eval_utils.py',
 'src/unifolm_wma/models/ddpms.py','src/unifolm_wma/modules/networks/wma_model.py','src/unifolm_wma/models/samplers/ddim.py'],
 'unifolm-vla': [
 'src/unifolm_vla/model/framework/unifolm_vla.py','src/unifolm_vla/model/modules/vlm/QWen2_5.py',
 'src/unifolm_vla/model/modules/action_model/DiT_ActionHeader.py','src/unifolm_vla/config/training/unifolm_vla_train.yaml',
 'scripts/eval_scripts/run_eval_libero.sh','experiments/LIBERO/unifolm_vla_inference.py','experiments/LIBERO/eval_libero.py',
 'scripts/run_scripts/run_unifolm_vla_train.sh','scripts/eval_scripts/run_real_eval_server.sh','deployment/model_server/run_real_eval_server.py'],
 'unifolm-wla': [
 'unifolm_wla/model/framework/VLM4A/QwenMMDiT.py','unifolm_wla/model/modules/vlm/QWen3.py',
 'unifolm_wla/model/modules/action_model/MMDiT_ActionHeader.py','unifolm_wla/model/modules/action_model/DiT_modules/mmdit.py',
 'unifolm_wla/model/modules/projector/robot_state.py','unifolm_wla/config/training/mmdit_finetune_frozen_vlm.yaml',
 'unifolm_wla/config/training/mmdit_lora_frozen_vlm.yaml','unifolm_wla/config/training/unifolm_wla_pretrain_multisource.yaml',
 'unifolm_wla/dataloader/multi_source_dataset/configs/unitree.yaml','examples/unifolm_wla/eval_files/unitree/eval_local_episode.py',
 'model_server/unifolm_wla_action_adapter.py','examples/unifolm_wla/train_files/run_finetune_mmdit_frozen_vlm.sh']}

def download(task):
    url,target=task
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(fetch(url))
    return {'url':url,'local_path':str(target.relative_to(ROOT.parent))}

if __name__=='__main__':
    tasks=[]
    for repo,paths in SELECTED.items():
        folder=ROOT/repo
        sha=json.loads((folder/'commit.json').read_text())['sha']
        tasks.extend((f'https://raw.githubusercontent.com/unitreerobotics/{repo}/{sha}/{path}',folder/path) for path in paths)
    with ThreadPoolExecutor(max_workers=8) as pool:
        manifest=list(pool.map(download,tasks))
    for name in ['UnifoLM-WMA-0-Base','UnifoLM-WMA-0-Dual','UnifoLM-VLM-Base','UnifoLM-VLA-Base','UnifoLM-VLA-Libero','UnifoLM-ER-1','UnifoLM-ER-Flow','UnifoLM-WLA-1.0-Base']:
        metadata=json.loads(fetch(f'https://huggingface.co/api/models/unitreerobotics/{name}?blobs=true'))
        folder=ROOT/'huggingface'/name;folder.mkdir(parents=True,exist_ok=True)
        (folder/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        sha=metadata['sha']
        files={item['rfilename'] for item in metadata['siblings']}
        print(name,'revision',sha,'weight_bytes',sum(item.get('size',0) for item in metadata['siblings'] if item['rfilename'].endswith(('.safetensors','.ckpt','.bin'))),flush=True)
        for path in ['README.md','config.json','config.yaml','tokenizer/config.json','dataset_statistics.json']:
            if path in files:
                manifest.append(download((f'https://huggingface.co/unitreerobotics/{name}/resolve/{sha}/{path}',folder/path)))
    (ROOT.parent/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Text sources saved:',len(manifest))
