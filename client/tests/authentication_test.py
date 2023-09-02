from telethon._impl.crypto import AuthKey
from telethon._impl.mtproto.authentication import (
    CreatedKey,
    _do_step1,
    _do_step2,
    _do_step3,
    create_key,
)


def test_successful_auth_key_gen_flow() -> None:
    # fmt: off
    step1_random = bytes.fromhex("4e44b426241e8b839153122d44585ac6")
    step1_request = bytes.fromhex("f18e7ebe4e44b426241e8b839153122d44585ac6")
    step1_response = bytes.fromhex("632416054e44b426241e8b839153122d44585ac665ba0b393e1094329eda2c42d62833030819546f942a11278d00000015c4b51c0300000003268d20df9858b2029f4ba16d109296216be86c022bb4c3")
    step2_random = bytes.fromhex("b9dce68b05ef760fa7edfefeff45aaa8afbac11dc3d333bc3132fd16ab816d63ed93c5bef9d0452add8164a2d5df5804277ee5a06fd4523372707ddbd8106d03766d76fb8bec672bdcddcd225f7766b83663b32a0fda1055175c5582edd10430937666be4fd15510ba5f19aa645973b6e4e9270efac25b58741635fe84dd0af07a4686f750bf34de1073f1e7fa24e9b01a76e537504bd52b8195e5b78c9af2baa982454e1a99eeae0f35944089ad12726d2433a2c18c9698a725364f9c4e939ce4f1aee3891e58b85de90c88cc2eaef5db1841a594c0edc13cb4b7480a7e564fe892f82282d03ed07eb5ceac6644247bb137241166fe194756dfcffd68c6c345696e9a94d85cd6ceb73a7927e7fdbec989ecef2bc1c3502759cca9e750955426")
    step2_request = bytes.fromhex("bee412d74e44b426241e8b839153122d44585ac665ba0b393e1094329eda2c42d62833030444b2e50d000000045e63ac8100000003268d20df9858b2fe0001007ec37ca8a84aa1b26d21bc8ac28b261ffa57b44e29f0d6722261e9b436059cc80ae9768a3ae4fbefe46cfbb76b88a1f80a1ebd95ae5d17bf655ed1015755e04c483a01cf4094a0830864054a71a0ac8a5ec34d6b24a69bf66c9654b32a8c65b0302718351b28f72a9a49610d5259b6edb6da37acc5fedc47d1a09c58df2c7eccbfaf54dfe123ebc253d9069f74e8be128051e5d280b3c9a5e8d3c6da344cb7374a6d410d4e088cc0eda3d8b1108ba4f4a85d79fbd2758000723780bc5459f59fd1cea1b511b77cc1411781d3feb57b14a97726cf3d2146cf43e648a69ff9cb5d48a31f543bd5bc3a023cf382d86d36bbfbbcb5e4a136acee25fd8e3e597e714d")
    step2_response = bytes.fromhex("5c07e8d04e44b426241e8b839153122d44585ac665ba0b393e1094329eda2c42d6283303fe500200fd064e91012ade621b26a48ac7dc8b2c8670ed67092a00fe8c936483e4b02822c3cc655aaffe00542e311df5abdaa645b1da85ca50a6c7b0e7cc7cb2b23d42c84e288bb3b5cfe313e1ebafe19833916df4d1f58dba62e0ac49cac17a31b8b0d57d43eefda546d67e80e311c4b213adec9635c73f75a18ffb26fb71391523bd5ddfcc8be51b36d6b2552394c511ec935d53811a981baca62a2b58cbfe96f1b35e118e5e17456994aea931839925c4578f281f3f129d28026ec80224617a9ca8c615a12fba9c53e774476567f07b01a59d2e6635e39c16dc0a54679f3b54b0482f1cbeac821147d93d7365f4e23fb5794eb5fd4ffdc6456638ea32f641f49ee705e7b0da71cb75753e2f4f80d5af07edb017948f332e34a9c5886b0c86281e0e7228d5a652a9faaf819f7686c099186169aaa377c136fac57b69b7f7b383aaece652f8dcb14e0dfb23e2a65330307a74c31c508cc504450fa208eee14d8bbead1c1f90ccfc183ae1d3345c62424ea3477776204e8fe69efbb6a27b168913d3babaca30aa1c9589d6655b2ad4cd59f67e9b3957ab3270d70afab9bd488a6c5f39ca739ca8947def00cdb8812152731710f5108235775a019d3b4986d6b720b05167b4ee731a10a29fc1e03c42e99d8ff5cf64f45070c2f5ce485ea5fddc281728b6e4d0dea561c9097e3f8a54b055b0c069a9f8207520f6429eb5225c985e3379f2cf6754f56d414fcd00d502e69223b911b915978e0890a9ef128715b828bf3fda3fee6c7b9b2621d971a6f7820f89f4c4c2ab29dec00007c3ec6cead64f7f5802d5e6a4a16a185cfbfced5351fa68380e")
    step3_random = bytes.fromhex("8fc3605a4604cbb5461fdeff439c761150083cdd502550558e92c730d46c9caf0b1b2d64d2c264942c50d98694fff604fdd2bd87f2cafb719bc55e65a1f60b08809660a650721c40d56fc9c792df1d463aad1718c6924b7bdffbe395f14633d33fc38ce47c18a1561b83a5c66d29f9e292637127471c3baab0028ae42796b689e53a7f9ab5f0ee6d3fb658d847c1abca509fc4ed0d45edbb1c946488910d8d78fa0767255b57a7c3898da8d26625bde40c5a0e80b581408ecd95a17d396dc7574a8ed3cbc4c085197ffaad29c18e577eb292aa8b98caa92efd6f9536049b5a7defc861e270eca90c55b9585405cb96f3e6ea754850b09e7a59ba5fd92d357982915d39752aaa2ec16b6cbde6a6c33971")
    step3_request = bytes.fromhex("1f5f04f54e44b426241e8b839153122d44585ac665ba0b393e1094329eda2c42d6283303fe500100def448d48c608480bab65df3f8990be8011f7b415a6f8113617bea749b8b0ea6a937987b18cc4dcce8197efdcf8d6ec6af7fc3364b4945df77e4a1ae9db7acea4abcd73247edb36bde20fc969c1d55717277afe0bc31a9ee99f7d822f91fa2dc69c868a19511b162d55e0814d0292b7708b67d57eb04569349d5a20ffe85c0141fc17e9bbbaf207bef56e66decda718c52c45273f868c2eff89bb06355cd515fbfe123d719b244234867d2889c9d0e4436ba644076e5014a78af60b2f0e1b30285f4f71539bcf8c506ccafd62cfcd1b040fe5e35bb30e519ad56d753100f604e3ea5d02409d74dd3ab0861227410f1e13591cf2a638347e6c6d0bcae14e0e8753313b51daee40a67407b5cc8b213856a290a0c7b6cda9ff9c58d69faaf6a748cff05512b69f1380f7a36843edecdc764048bc16d9808f353a9caf6d49ca8b717c8f6de037518a444931a7da2b80f16d0")
    step3_response = bytes.fromhex("34f7cb3b4e44b426241e8b839153122d44585ac665ba0b393e1094329eda2c42d628330313b781a0de4ab6bc7ab414cbe13f9f86")
    expected_auth_key = bytes.fromhex("7582e48ad36cd6eef7944ac9bd7027de9ee3202543b68850ac01e1221350f7174e6c3771c9d86b3075f777539c23d053e9da9a1510d49e8fa0ad76a016ce28bfe3543dde69959bc682dab762b95a36629a8438e65baa53cc79b551c23d555c7675a36f4ece90882ece497d28a903409b780a8a80516cb0f8534fee3a67530beb2b1929626e07c2a052c4870b18b0a626606ca05cb13668a65aee3fa32cbebf1b3a56532138cb22c017cac44a292021902eea9b9f906c6be19c9203c7bb3ebc5f1b2044d0a90cb008f7248c3ae4449e0895b6090abb04c24131c2948bd27d879ecb934e50a46671f987653385ab388e4fa1ddd4c95743111e08bf11fef1f8f739")
    # fmt: on

    request, step1 = _do_step1(step1_random)
    assert request == step1_request
    response = step1_response

    request, step2 = _do_step2(step1, response, step2_random)
    assert request == step2_request
    response = step2_response

    step3_now = 1693436740
    request, step3 = _do_step3(step2, response, step3_random, step3_now)
    assert request == step3_request
    response = step3_response

    finished = create_key(step3, response)
    assert finished == CreatedKey(
        auth_key=AuthKey.from_bytes(expected_auth_key),
        time_offset=0,
        first_salt=4459407212920268508,
    )
